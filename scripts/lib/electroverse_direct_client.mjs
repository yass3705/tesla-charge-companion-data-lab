import { performance } from 'node:perf_hooks';

export class DirectElectroverseClient {
  constructor({
    apiKey = process.env.ELECTROVERSE_API_KEY,
    endpoint = process.env.ELECTROVERSE_GRAPHQL_URL || 'https://api.electroverse.com/graphql/',
    source = process.env.ELECTROVERSE_SOURCE || 'android',
    appVersion = process.env.ELECTROVERSE_APP_VERSION || '2026.09.08',
    timeoutMs = Number(process.env.ELECTROVERSE_TIMEOUT_MS || 45000),
  } = {}) {
    if (!apiKey) throw new Error('ELECTROVERSE_API_KEY is required');
    this.apiKey = apiKey;
    this.endpoint = endpoint;
    this.source = source;
    this.appVersion = appVersion;
    this.timeoutMs = timeoutMs;
  }

  headers(extra = {}) {
    return {
      'Api-Key': this.apiKey,
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'source': this.source,
      'X-App-Version': this.appVersion,
      ...extra,
    };
  }

  async request(query, variables = {}, { attempts = 3 } = {}) {
    let last;
    for (let attempt = 1; attempt <= attempts; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      const t0 = performance.now();
      try {
        const res = await fetch(this.endpoint, {
          method: 'POST',
          headers: this.headers(),
          body: JSON.stringify({ query, variables }),
          signal: controller.signal,
        });
        const text = await res.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        const out = {
          status: res.status,
          ms: Math.round(performance.now() - t0),
          bytes: Buffer.byteLength(text),
          json,
          text: json ? null : text.slice(0, 1000),
          attempt,
          responseHeaders: {
            retryAfter: res.headers.get('retry-after'),
            rateLimitLimit: res.headers.get('ratelimit-limit') || res.headers.get('x-ratelimit-limit'),
            rateLimitRemaining: res.headers.get('ratelimit-remaining') || res.headers.get('x-ratelimit-remaining'),
            rateLimitReset: res.headers.get('ratelimit-reset') || res.headers.get('x-ratelimit-reset'),
          },
        };
        if (res.ok && json) return out;
        last = out;
        if (![429, 500, 502, 503, 504].includes(res.status) || attempt === attempts) return out;
      } catch (error) {
        last = {
          status: 0,
          ms: Math.round(performance.now() - t0),
          bytes: 0,
          json: null,
          text: null,
          attempt,
          error: error instanceof Error ? error.message : String(error),
        };
        if (attempt === attempts) return last;
      } finally {
        clearTimeout(timer);
      }
      await new Promise(r => setTimeout(r, [750, 2000, 5000][attempt - 1] || 5000));
    }
    return last;
  }
}

export const PRICE_COMPONENT_FIELDS = `
  __typename
  formattedValue
`;

export const CONNECTOR_FIELDS = `
  pk kilowatts speed isChargingFree
  standard { ... on EJNConnectorStandardType { name humanName } }
  priceComponents { ${PRICE_COMPONENT_FIELDS} }
  complexPricingDetail {
    currency
    restrictions {
      restrictionTypes
      timeRestrictions { startTime endTime }
      durationRestrictions { minDurationSeconds maxDurationSeconds }
      dateRestrictions { startDate endDate }
      weekdayRestrictions { daysOfWeek }
      priceComponents { ${PRICE_COMPONENT_FIELDS} }
    }
  }
`;

export const EVSE_FIELDS = `
  pk physicalReference status
  connectors { edges { node { ${CONNECTOR_FIELDS} } } }
`;

export const TARIFF_LOCATION_FIELDS = `
  chargingLocationPk
  evses { edges { node { ${EVSE_FIELDS} } } }
`;

export function aliasBatchQuery(pks) {
  return `query ElectroverseTariffBatch {
    ${pks.map((pk, i) => `s${i}: chargingLocation(pk: ${JSON.stringify(String(pk))}) { ${TARIFF_LOCATION_FIELDS} }`).join('\n')}
  }`;
}

export const SINGLE_LOCATION_QUERY = `
  query ElectroverseTariffSingle($pk: String!) {
    chargingLocation(pk: $pk) { ${TARIFF_LOCATION_FIELDS} }
  }
`;

export const PAGED_LOCATION_QUERY = `
  query ElectroverseTariffPaged($pk: String!, $first: Int!, $after: String) {
    chargingLocation(pk: $pk) {
      chargingLocationPk
      evses(first: $first, after: $after) {
        edges { cursor node { ${EVSE_FIELDS} } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
`;
