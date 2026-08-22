import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const OUT = 'artifacts/saint-cyr-live-status';
const ELECTRA_URL = 'https://emsp.go-electra.com/graphql';
const ELECTROVERSE_URL = 'https://electroverse.com/api/proxy/graphql';
await fs.mkdir(OUT, { recursive: true });

const targets = {
  electra: [
    {
      key: 'charles-michel-alize-legacy',
      id: 'e006af07-6b4e-4e11-badd-3ce499ff7b86',
      expectedName: "SAINT CYR l'ECOLE - Rue Charles Michel"
    },
    {
      key: 'charles-michel-electric55-current',
      id: '3dcddb20-3132-4488-ad13-e98985032e56',
      expectedName: "RUE CHARLES MICHELS - SAINT-CYR-L'ECOLE"
    }
  ],
  electroverse: [
    {
      key: 'lattre-de-tassigny-alize',
      pk: '2423238',
      expectedName: "SAINT CYR l'ECOLE - Rue de Lattre de Tassigny"
    },
    {
      key: 'nearby-electric55-current',
      pk: '4402244',
      expectedName: 'Electric 55 replacement near Charles Michel / Lattre de Tassigny'
    },
    {
      key: 'lidl-aerostation-maritime',
      pk: '1813284',
      expectedName: "Rue de l'Aérostation Maritime · SAINT CYR L'ECOLE"
    }
  ]
};

const ELECTRA_QUERY = `query Target($id:ID!){
  location(id:$id){
    id name address city postalCode country coordinates{latitude longitude}
    cpo{name} operator{name} connectorTypes maxPower
    evses{id status physicalReference evseId}
    chargeTariffs{
      chargeTariffId currency currentPricePerKwh
      elements{restrictions{dayOfWeek startTime endTime} priceComponents{type price}}
    }
  }
}`;

const ELECTROVERSE_QUERY = `query Target($pk:String!){
  chargingLocation(pk:$pk){
    pk chargingLocationPk externalId name address city postalCode country coordinates
    openingHours{twentyFourSeven regularHours{weekday periodBegin periodEnd}}
    alerts{type content}
    operator{pk name}
    evses{
      totalCount
      edges{node{
        pk physicalReference status
        connectors{edges{node{pk kilowatts speed standard{name humanName}}}}
      }}
    }
  }
}`;

const compactStatus = statuses => {
  const clean = statuses.filter(Boolean).map(String);
  if (!clean.length) return 'UNKNOWN';
  const unavailable = new Set(['OUTOFORDER', 'INOPERATIVE', 'REMOVED', 'UNKNOWN']);
  return clean.every(s => unavailable.has(s.toUpperCase())) ? 'HORS_SERVICE' : 'DISPONIBLE';
};

const weekdayNames = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];
function parisNowParts(date = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Paris', weekday: 'long', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
  }).formatToParts(date).filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
  return { weekday: parts.weekday.toUpperCase(), time: `${parts.hour}:${parts.minute}` };
}
function openingState(openingHours, date = new Date()) {
  if (!openingHours) return { known: false, isOpen: null, reason: 'opening hours missing' };
  if (openingHours.twentyFourSeven) return { known: true, isOpen: true, reason: '24/7' };
  const regular = openingHours.regularHours ?? [];
  if (!regular.length) return { known: false, isOpen: null, reason: 'regular hours missing' };
  const now = parisNowParts(date);
  const todayIndex = weekdayNames.indexOf(now.weekday);
  const today = regular.filter(x => {
    const raw = String(x.weekday ?? '').toUpperCase();
    return raw === now.weekday || Number(raw) === todayIndex || Number(raw) === (todayIndex || 7);
  });
  const hhmm = value => String(value ?? '').slice(0, 5);
  const isOpen = today.some(x => {
    const begin = hhmm(x.periodBegin);
    const end = hhmm(x.periodEnd);
    if (!begin || !end) return false;
    return begin <= end ? now.time >= begin && now.time < end : now.time >= begin || now.time < end;
  });
  return { known: true, isOpen, reason: isOpen ? 'inside regular hours' : 'outside regular hours', parisNow: now, today };
}

async function postJson(url, query, variables, extraHeaders = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'application/json',
      'user-agent': 'tesla-charge-companion-targeted-status/1.0',
      ...extraHeaders
    },
    body: JSON.stringify({ query, variables }),
    signal: AbortSignal.timeout(30000)
  });
  const text = await response.text();
  let json = null;
  try { json = JSON.parse(text); } catch {}
  return { httpStatus: response.status, json, rawText: json ? undefined : text.slice(0, 1000) };
}

const electra = [];
for (const target of targets.electra) {
  const response = await postJson(ELECTRA_URL, ELECTRA_QUERY, { id: target.id });
  const location = response.json?.data?.location ?? null;
  const statuses = (location?.evses ?? []).map(x => x?.status);
  electra.push({
    source: 'electra',
    target,
    queriedAt: new Date().toISOString(),
    httpStatus: response.httpStatus,
    errors: response.json?.errors ?? null,
    found: Boolean(location),
    normalizedTccStatus: location ? compactStatus(statuses) : 'UNKNOWN',
    evseStatuses: statuses,
    location
  });
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ locale: 'fr-FR' });
const page = await context.newPage();
await page.goto('https://electroverse.com/map', { waitUntil: 'domcontentloaded', timeout: 90000 });
await page.waitForTimeout(2500);

async function fetchElectroverse(pk) {
  return page.evaluate(async ({ url, query, pk }) => {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ query, variables: { pk } })
    });
    const text = await response.text();
    let json = null;
    try { json = JSON.parse(text); } catch {}
    return { httpStatus: response.status, json, rawText: json ? undefined : text.slice(0, 1000) };
  }, { url: ELECTROVERSE_URL, query: ELECTROVERSE_QUERY, pk });
}

const electroverse = [];
for (const target of targets.electroverse) {
  const response = await fetchElectroverse(target.pk);
  const location = response.json?.data?.chargingLocation ?? null;
  const evses = (location?.evses?.edges ?? []).map(x => x?.node).filter(Boolean);
  const statuses = evses.map(x => x?.status);
  const rawNormalizedStatus = location ? compactStatus(statuses) : 'UNKNOWN';
  const access = openingState(location?.openingHours);
  const scheduledClosureOverride = rawNormalizedStatus === 'HORS_SERVICE' && access.known && access.isOpen === false;
  electroverse.push({
    source: 'electroverse',
    target,
    queriedAt: new Date().toISOString(),
    httpStatus: response.httpStatus,
    errors: response.json?.errors ?? null,
    found: Boolean(location),
    rawNormalizedStatus,
    scheduledClosureOverride,
    normalizedTccStatus: scheduledClosureOverride ? 'DISPONIBLE' : rawNormalizedStatus,
    access,
    evseStatuses: statuses,
    location
  });
}
await browser.close();

const result = {
  generatedAt: new Date().toISOString(),
  purpose: 'Live targeted status verification for the two suspicious Saint-Cyr-l’Ecole legacy Alize locations and their nearby Electric 55 replacement records.',
  tccRule: {
    DISPONIBLE: 'At least one EVSE is usable, occupied, charging or reserved.',
    HORS_SERVICE: 'All returned EVSEs are OUTOFORDER/INOPERATIVE/REMOVED/UNKNOWN.',
    openingHours: 'A scheduled closure must not be converted to HORS_SERVICE.'
  },
  electra,
  electroverse
};

await fs.writeFile(`${OUT}/status-result.json`, JSON.stringify(result, null, 2) + '\n');
const lines = [
  '# Saint-Cyr live status check',
  '',
  `Generated: ${result.generatedAt}`,
  '',
  '| Source | Target | Found | Raw EVSE statuses | TCC status |',
  '|---|---|---:|---|---|',
  ...[...electra, ...electroverse].map(x =>
    `| ${x.source} | ${x.location?.name ?? x.target.expectedName} | ${x.found ? 'yes' : 'no'} | ${x.evseStatuses.join(', ') || 'none'} | ${x.normalizedTccStatus} |`
  ),
  ''
];
await fs.writeFile(`${OUT}/summary.md`, lines.join('\n'));
console.log(lines.join('\n'));
