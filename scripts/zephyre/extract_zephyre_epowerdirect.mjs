#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

const IRVE_URL = process.env.IRVE_URL ||
  "https://www.data.gouv.fr/api/1/datasets/r/eb76d20a-8501-400e-b336-d85724de5435";
const BFF = process.env.EPOWERDIRECT_BFF ||
  "https://api.services-emobility.com/pay/api";
const OUTPUT = process.argv[2] ||
  "data/zephyre/france/zephyre-france-current.json";
const NEARBY_CONCURRENCY = Number(process.env.NEARBY_CONCURRENCY || 8);
const DETAIL_CONCURRENCY = Number(process.env.DETAIL_CONCURRENCY || 10);

const normalizeEvse = (value = "") =>
  String(value).replaceAll("*", "").trim().toUpperCase();

function parseCsv(text, onRow) {
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
      continue;
    }

    if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n") {
      row.push(field);
      onRow(row);
      row = [];
      field = "";
    } else if (c !== "\r") {
      field += c;
    }
  }

  if (field.length || row.length) {
    row.push(field);
    onRow(row);
  }
}

async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let cursor = 0;
  async function worker() {
    while (true) {
      const index = cursor++;
      if (index >= items.length) return;
      out[index] = await fn(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return out;
}

function signatureOf(tariff) {
  const priceComponents = (tariff?.priceComponents || []).map((p) => ({
    unit: p.priceUnit ?? null,
    price: p.price ?? null,
    freeParkingCostMinutes: p.freeParkingCostMinutes || 0,
    restrictionStartTime: p.restrictionStartTime || null,
    restrictionEndTime: p.restrictionEndTime || null,
    taxAmount: p.taxAmount ?? null,
  }));
  return {
    currency: tariff?.currency || null,
    currentType: tariff?.currentType || null,
    priceComponents,
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`${response.status} ${url}: ${body.slice(0, 240)}`);
  }
  return JSON.parse(body);
}

async function main() {
  const startedAt = new Date().toISOString();
  const irveResponse = await fetch(IRVE_URL, { redirect: "follow" });
  if (!irveResponse.ok) {
    throw new Error(`IRVE download failed: ${irveResponse.status}`);
  }
  const irveFinalUrl = irveResponse.url;
  const csv = await irveResponse.text();

  let header = null;
  let index = null;
  const latestByEvse = new Map();

  parseCsv(csv, (row) => {
    if (!header) {
      header = row;
      index = Object.fromEntries(header.map((name, i) => [name, i]));
      return;
    }
    const evse = normalizeEvse(row[index.id_pdc_itinerance]);
    if (!evse.startsWith("FRZP1")) return;

    const candidate = {
      evse,
      evseId: row[index.id_pdc_itinerance] || null,
      stationId: row[index.id_station_itinerance] || null,
      stationLocalId: row[index.id_station_local] || null,
      stationName: row[index.nom_station] || null,
      operator: row[index.nom_operateur] || null,
      address: row[index.adresse_station] || null,
      latitude: Number(row[index.consolidated_latitude]),
      longitude: Number(row[index.consolidated_longitude]),
      nominalPowerKw: Number(row[index.puissance_nominale]) || null,
      irveTarification: row[index.tarification] || null,
      dateMaj: row[index.date_maj] || null,
      lastModified: row[index.last_modified] || null,
      datasetId: row[index.datagouv_dataset_id] || null,
      resourceId: row[index.datagouv_resource_id] || null,
    };
    if (!Number.isFinite(candidate.latitude) || !Number.isFinite(candidate.longitude)) {
      return;
    }

    const old = latestByEvse.get(evse);
    const stamp = candidate.lastModified || candidate.dateMaj || "";
    const oldStamp = old ? (old.lastModified || old.dateMaj || "") : "";
    if (!old || stamp > oldStamp) latestByEvse.set(evse, candidate);
  });

  const irve = [...latestByEvse.values()];
  const coordinateMap = new Map();
  for (const row of irve) {
    const key = `${row.latitude.toFixed(6)},${row.longitude.toFixed(6)}`;
    if (!coordinateMap.has(key)) {
      coordinateMap.set(key, { latitude: row.latitude, longitude: row.longitude });
    }
  }
  const coordinates = [...coordinateMap.values()];

  const nearbyErrors = [];
  const liveByInternalName = new Map();
  const liveByCoordinate = new Map();

  const nearby = await mapLimit(coordinates, NEARBY_CONCURRENCY, async (coord) => {
    try {
      const stations = await fetchJson(`${BFF}/stations/nearby`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          latitude: coord.latitude,
          longitude: coord.longitude,
        }),
      });
      return { coord, stations };
    } catch (error) {
      nearbyErrors.push({
        latitude: coord.latitude,
        longitude: coord.longitude,
        error: String(error),
      });
      return { coord, stations: [] };
    }
  });

  for (const { coord, stations } of nearby) {
    const coordKey = `${coord.latitude.toFixed(6)},${coord.longitude.toFixed(6)}`;
    const here = [];
    for (const station of stations || []) {
      for (const cp of station.chargePoints || []) {
        const evse = normalizeEvse(cp.evseId);
        if (!evse.startsWith("FRZP1")) continue;
        const live = {
          evse,
          evseId: cp.evseId,
          internalName: cp.name,
          status: cp.evseStatus || null,
          available: cp.available ?? null,
          multitenantDirectPaymentAvailable:
            cp.multitenantDirectPaymentAvailable ?? null,
          paymentMethods: cp.paymentMethods || [],
          maxChargingPowerKw: Number(cp.maxChargingPower) || null,
          nearbyAddress: station.address || null,
          queryLatitude: coord.latitude,
          queryLongitude: coord.longitude,
        };
        here.push(live);
        liveByInternalName.set(live.internalName, live);
      }
    }
    liveByCoordinate.set(coordKey, here);
  }

  const live = [...liveByInternalName.values()];
  const detailErrors = [];
  const details = (
    await mapLimit(live, DETAIL_CONCURRENCY, async (item) => {
      try {
        const station = await fetchJson(
          `${BFF}/stations/chargepoint/${encodeURIComponent(item.internalName)}`
        );
        const chargePoints = station.chargePoints || [];
        const cp =
          chargePoints.find((x) => x.name === item.internalName) ||
          chargePoints.find((x) => normalizeEvse(x.evseId) === item.evse) ||
          chargePoints[0];

        if (!cp) throw new Error("No charge point in station detail response");

        const tariff = cp.tariff
          ? {
              currency: cp.tariff.currency || station.currency || null,
              currentType: cp.tariff.currentType || null,
              invalidationTimestamp: cp.tariff.invalidationTimestamp || null,
              priceComponents: (cp.tariff.priceComponents || []).map((p) => ({
                price: p.price ?? null,
                priceUnit: p.priceUnit || null,
                freeParkingCostMinutes: p.freeParkingCostMinutes || 0,
                restrictionStartTime: p.restrictionStartTime || null,
                restrictionEndTime: p.restrictionEndTime || null,
                taxAmount: p.taxAmount ?? null,
              })),
            }
          : null;

        const irveMatch = latestByEvse.get(normalizeEvse(cp.evseId)) || null;
        return {
          evse: normalizeEvse(cp.evseId),
          evseId: cp.evseId,
          internalName: cp.name,
          provider: station.provider
            ? { id: station.provider.id || null, name: station.provider.name || null }
            : null,
          address: station.address || item.nearbyAddress || null,
          vat: station.vat ?? null,
          currency: station.currency || tariff?.currency || null,
          status: cp.evseStatus || item.status || null,
          available: cp.available ?? item.available ?? null,
          multitenantDirectPaymentAvailable:
            cp.multitenantDirectPaymentAvailable ??
            item.multitenantDirectPaymentAvailable ??
            null,
          paymentMethods: cp.paymentMethods || item.paymentMethods || [],
          maxChargingPowerKw:
            Number(cp.maxChargingPower) || item.maxChargingPowerKw || null,
          tariff,
          irve: irveMatch,
        };
      } catch (error) {
        detailErrors.push({
          evse: item.evse,
          internalName: item.internalName,
          error: String(error),
        });
        return null;
      }
    })
  ).filter(Boolean);

  const signatureKeyToMembers = new Map();
  for (const detail of details) {
    const signature = signatureOf(detail.tariff);
    const key = JSON.stringify(signature);
    if (!signatureKeyToMembers.has(key)) {
      signatureKeyToMembers.set(key, { signature, evses: [] });
    }
    signatureKeyToMembers.get(key).evses.push(detail.evse);
  }

  const tariffSignatures = [...signatureKeyToMembers.values()]
    .sort((a, b) => JSON.stringify(a.signature).localeCompare(JSON.stringify(b.signature)))
    .map((entry, i) => ({
      id: `T${i + 1}`,
      count: entry.evses.length,
      definition: entry.signature,
      exampleEvses: entry.evses.slice(0, 5),
    }));

  const signatureLookup = new Map(
    tariffSignatures.map((s) => [JSON.stringify(s.definition), s.id])
  );
  for (const detail of details) {
    detail.tariffSignature = signatureLookup.get(
      JSON.stringify(signatureOf(detail.tariff))
    );
  }

  const liveEvse = new Set(details.map((x) => x.evse));
  const unresolved = irve
    .filter((x) => !liveEvse.has(x.evse))
    .map((row) => {
      const key = `${row.latitude.toFixed(6)},${row.longitude.toFixed(6)}`;
      const replacementCandidates = (liveByCoordinate.get(key) || []).map((x) => ({
        evse: x.evse,
        evseId: x.evseId,
        internalName: x.internalName,
        status: x.status,
      }));
      return {
        ...row,
        reason: replacementCandidates.length
          ? "not_exposed_by_epowerdirect_evse_replaced_or_stale_same_coordinate"
          : "not_exposed_by_epowerdirect_fail_closed",
        replacementCandidates,
      };
    });

  const unresolvedByDataset = {};
  for (const row of unresolved) {
    const key = row.datasetId || "unknown";
    unresolvedByDataset[key] = (unresolvedByDataset[key] || 0) + 1;
  }

  const report = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    startedAt,
    country: "FR",
    operator: {
      canonical: "Zephyre",
      partyId: "FR*ZP1",
    },
    sources: {
      irve: {
        requestedUrl: IRVE_URL,
        resolvedUrl: irveFinalUrl,
      },
      epowerDirect: {
        bff: BFF,
        nearby: "POST /stations/nearby {latitude,longitude}",
        detail: "GET /stations/chargepoint/{internalName}",
        authentication: "none",
      },
    },
    coverage: {
      irveUniqueEvse: irve.length,
      uniqueSeedCoordinates: coordinates.length,
      liveDirectEvse: details.length,
      liveDirectPaymentEnabled: details.filter(
        (x) => x.multitenantDirectPaymentAvailable === true
      ).length,
      liveTariffPresent: details.filter(
        (x) => x.tariff && x.tariff.priceComponents.length
      ).length,
      detailErrors: detailErrors.length,
      nearbyErrors: nearbyErrors.length,
      unresolvedIrveEvse: unresolved.length,
      unresolvedByDataset,
      uniqueTariffSignatures: tariffSignatures.length,
    },
    policy: {
      directTariffScope: "exact EVSE returned by ePowerDirect only",
      nationalConstantAllowed: false,
      unresolved:
        "fail closed; do not infer price from same-site or national tariff; use TCC fallback",
      bindingPricingOfferTokenStored: false,
    },
    tariffSignatures,
    stations: details.sort((a, b) => a.evse.localeCompare(b.evse)),
    unresolved,
    errors: {
      nearby: nearbyErrors,
      detail: detailErrors,
    },
  };

  await fs.mkdir(path.dirname(OUTPUT), { recursive: true });
  await fs.writeFile(OUTPUT, JSON.stringify(report, null, 2) + "\n", "utf8");

  console.log(
    JSON.stringify({
      output: OUTPUT,
      coverage: report.coverage,
      providers: [...new Set(details.map((x) => x.provider?.name).filter(Boolean))],
    })
  );

  if (nearbyErrors.length || detailErrors.length) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
