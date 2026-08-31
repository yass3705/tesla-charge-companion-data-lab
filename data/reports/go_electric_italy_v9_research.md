# Go Electric Stations SRLS — Italy V9 research

## Priority

Current stable Italy V9 exact-EVSE audit identifies **2,413 PUN EVSE across 1,136 stations** under `Go Electric Stations SRLS` with no validated CPO-direct tariff. This is the largest non-Tesla direct-tariff gap by EVSE count.

## Consumer channel

Go Electric Stations SRLS operates the NextCharge service/app. Public NextCharge documentation states that charging tariffs are shown for each individual connector before session start and may contain multiple additive components: session, time and energy. It also states that tariffs may change without advance notice and that some stations can have an additional post-session/parking charge.

Sources:
- https://nextcharge.app/apps/map/apis/terms/v1.4/termsAndConditions.php?appearanceTheme=auto&lang=it
- https://nextcharge.app/map?nextcharge=only
- https://nextcharge.app/

## V9 safety policy

Do **not** create a national flat Go Electric CPO tariff from third-party summaries or isolated screenshots.

A Go Electric direct offer is publishable only when all of the following are true:
1. PUN physical identity is exact at EVSE/connector scope.
2. Go Electric is the physical CPO for that EVSE.
3. The consumer price is obtained from a public/native NextCharge surface and is attributable to that exact connector.
4. All additive components needed for final cost are captured (energy, time, session and post-charge/parking when applicable).
5. The tariff observation has a timestamp/source and fails closed when a station-specific component is unknown.

NextCharge roaming prices for third-party CPOs remain `emsp` and must never be promoted to Go Electric CPO-direct tariffs.

## Current task

The first automated step is a read-only discovery probe of the public NextCharge web map assets. Its only goal is to identify public station/connector/tariff endpoints that can support exact-EVSE extraction. It performs no authentication, charging-session action or remote mutation.
