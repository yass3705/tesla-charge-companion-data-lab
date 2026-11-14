// Technical response completeness only. No price or historical-volume checks.
export function completeLocation(response, field, expectedPk, {paged=false}={}) {
  if (!(response?.status >= 200 && response.status < 300)) return null;
  if (response.json?.errors!=null && !Array.isArray(response.json.errors)) return null;
  if (response.json?.errors?.some(error=>!Array.isArray(error?.path)||error.path[0]===field)) return null;
  const location=response.json?.data?.[field];
  if (!location || String(location.chargingLocationPk)!==String(expectedPk) || !Array.isArray(location.evses?.edges)) return null;
  const evseIds=new Set();
  for (const edge of location.evses.edges) {
    const evse=edge?.node;
    if (!evse || !Array.isArray(evse.connectors?.edges)) return null;
    if (evse.pk!=null) { const id=String(evse.pk); if(evseIds.has(id))return null; evseIds.add(id); }
    const connectors=new Set();
    for (const item of evse.connectors.edges) {
      if (!item?.node) return null;
      if (item.node.pk!=null) { const id=String(item.node.pk); if(connectors.has(id))return null; connectors.add(id); }
    }
  }
  if (paged && (typeof location.evses.pageInfo?.hasNextPage!=='boolean' ||
      location.evses.pageInfo.hasNextPage && !location.evses.pageInfo.endCursor)) return null;
  return location;
}
