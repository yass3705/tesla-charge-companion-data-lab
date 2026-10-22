/**
 * TCC Electroverse connector policy. Keep the strict allowlist centralized:
 * French domestic E/F, Type 2 and CCS Combo 2 only.
 * Unknown types, CHAdeMO, Type 1 and CCS Combo 1 fail closed.
 */
const ALLOWED = new Set([
  'DOMESTIC_E', 'DOMESTIC_F', 'DOMESTIC_EF', 'DOMESTIC_E_F',
  'SCHUKO', 'CEE_7_3', 'CEE_7_5', 'EF', 'E_F', 'TYPE_E', 'TYPE_F',
  'IEC_62196_T2', 'TYPE_2', 'TYPE2', 'T2',
  'IEC_62196_T2_COMBO', 'CCS', 'CCS2', 'CCS_2', 'COMBO_2',
]);

export function electroverseConnectorStandard(connectorOrStandard) {
  const raw = connectorOrStandard?.standard ?? connectorOrStandard;
  const value = (raw && typeof raw === 'object') ? raw.name : raw;
  return String(value ?? '').trim().toUpperCase().replace(/[\s-]+/g, '_');
}

export function isSupportedElectroverseConnector(connector) {
  return ALLOWED.has(electroverseConnectorStandard(connector));
}

export function filterSupportedElectroverseConnectors(connectors) {
  return (Array.isArray(connectors) ? connectors : [])
    .filter(isSupportedElectroverseConnector);
}

export const ELECTROVERSE_SUPPORTED_CONNECTOR_CLASSES = Object.freeze(['E/F', 'Type 2', 'CCS Combo 2']);
