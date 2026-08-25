# Powerdot direct QR probe v2

- Powerdot IRVE rows: **14175**
- Unique stations: **1177**
- EVSE/PDC: **14175**
- Stations with IRVE tarification text: **1**
- QR probes: **202**
- QR HTTP 200: **4**
- Derived QR HTTP 200: **2**

## Known public QR probes

- Mr Bricolage Champniers | MRB_CHP_KPC20001 | HTTP 200 | len 3863 | final https://adhoc.pwrdt.com/?charger_name=MRB_CHP_KPC20001
- Netto Soustons | NET_SST_KPS20001 | HTTP 200 | len 3863 | final https://adhoc.pwrdt.com/?charger_name=NET_SST_KPS20001

## Successful derived QR candidates

- ACE Hôtel Paris - Sud Villabé | ACE_VIL_SLM10001 | https://adhoc.pwrdt.com/?charger_name=ACE_VIL_SLM10001
- Action - Verneuil d'Avre | ACT_VDD_KPS20001 | https://adhoc.pwrdt.com/connector-selection?charger_name=ACT_VDD_KPS20001

## Frontend/API findings

- Asset: https://adhoc.pwrdt.com/assets/index-B36_HfRJ.js | HTTP 200 | len 420534
  - URL: http://www.powerdot.pt
  - URL: http://www.powerdot.pt</Action>
  - URL: https://api.mapbox.com/geocoding/v5/mapbox.places
  - URL: https://api.mapbox.com/search/searchbox/v1
  - URL: https://api.pwrdt.com
  - URL: https://auth.powerdot.eu/realms
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.pt
  - URL: https://www.powerdot.pt</Action>,
  - Snippet: js","assets/vendor-analytics-pR5Mwgig.js","assets/NeedHelpChoosingChargerPopup-DKH4GCyf.js","assets/ConnectorUnavailablePopup-D2gccAJB.js","assets/_terminal-CwgZ5tJ7.js","assets/UnpaidDebtOverlayManager-BwX9FkjU.js","assets/TutorialPopup-BqDWCees.js","assets/LazyCountryPickerBottomSheet-j
  - Snippet: ew2op.js","assets/vendor-payments-Dn6H7tOa.js","assets/NetworkRatesBottomSheet-CnWikIl2.js","assets/ConnectorsCount-C48C1A3n.js","assets/SectionTitle-D0KDrQOV.js","assets/InlineRateExperience-CPirSG02.js","assets/GetDiscountCodePopup-DkREnbMv.js","assets/useChargingCurveService-CSjfCjAT.j
  - Snippet: CSjfCjAT.js","assets/terminal-charging-CACr3o-a.js","assets/SessionStateBanner-BB3_4Rp0.js","assets/PricingInfoBottomSheet-Di9ACFNL.js","assets/FeatureInfoDrawer-CnM3r4DG.js","assets/subscription-plans-_yQtFhoH.js","assets/SubscriptionPlansBottomSheet-nIXIhVkp.js","assets/_map-auth-BDsr
  - Snippet: ,"assets/session-summary-Bkk-E_yT.js","assets/session-payment-failed-BPscH3QE.js","assets/preparing-connector-Dl-AzDQO.js","assets/pre-authorization-B9r8xpc3.js","assets/ChangeAmountBottomSheet-xa0g9wOr.js","assets/StateBanner-D0kOVRrG.js","assets/payment-D8dFjNU1.js","assets/LazyPaymentE
  - Snippet: Cvtvg7ML.js","assets/location-D6ivoFSD.js","assets/HowToGeoLocationBottomSheet-B-GQE-xo.js","assets/connector-selection-CuEhC9yd.js","assets/coming-soon-Gb4jAkq-.js","assets/charging--g5huhDj.js","assets/subscription-details-pZKQc8xU.js","assets/setup-subscription-C9tRP1Dv.js","assets/Cou
- Asset: https://adhoc.pwrdt.com/assets/index-B36_HfRJ.js | HTTP 200 | len 420534
  - URL: http://www.powerdot.pt
  - URL: http://www.powerdot.pt</Action>
  - URL: https://api.mapbox.com/geocoding/v5/mapbox.places
  - URL: https://api.mapbox.com/search/searchbox/v1
  - URL: https://api.pwrdt.com
  - URL: https://auth.powerdot.eu/realms
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.pt
  - URL: https://www.powerdot.pt</Action>,
  - Snippet: js","assets/vendor-analytics-pR5Mwgig.js","assets/NeedHelpChoosingChargerPopup-DKH4GCyf.js","assets/ConnectorUnavailablePopup-D2gccAJB.js","assets/_terminal-CwgZ5tJ7.js","assets/UnpaidDebtOverlayManager-BwX9FkjU.js","assets/TutorialPopup-BqDWCees.js","assets/LazyCountryPickerBottomSheet-j
  - Snippet: ew2op.js","assets/vendor-payments-Dn6H7tOa.js","assets/NetworkRatesBottomSheet-CnWikIl2.js","assets/ConnectorsCount-C48C1A3n.js","assets/SectionTitle-D0KDrQOV.js","assets/InlineRateExperience-CPirSG02.js","assets/GetDiscountCodePopup-DkREnbMv.js","assets/useChargingCurveService-CSjfCjAT.j
  - Snippet: CSjfCjAT.js","assets/terminal-charging-CACr3o-a.js","assets/SessionStateBanner-BB3_4Rp0.js","assets/PricingInfoBottomSheet-Di9ACFNL.js","assets/FeatureInfoDrawer-CnM3r4DG.js","assets/subscription-plans-_yQtFhoH.js","assets/SubscriptionPlansBottomSheet-nIXIhVkp.js","assets/_map-auth-BDsr
  - Snippet: ,"assets/session-summary-Bkk-E_yT.js","assets/session-payment-failed-BPscH3QE.js","assets/preparing-connector-Dl-AzDQO.js","assets/pre-authorization-B9r8xpc3.js","assets/ChangeAmountBottomSheet-xa0g9wOr.js","assets/StateBanner-D0kOVRrG.js","assets/payment-D8dFjNU1.js","assets/LazyPaymentE
  - Snippet: Cvtvg7ML.js","assets/location-D6ivoFSD.js","assets/HowToGeoLocationBottomSheet-B-GQE-xo.js","assets/connector-selection-CuEhC9yd.js","assets/coming-soon-Gb4jAkq-.js","assets/charging--g5huhDj.js","assets/subscription-details-pZKQc8xU.js","assets/setup-subscription-C9tRP1Dv.js","assets/Cou
- Asset: https://adhoc.pwrdt.com/assets/index-B36_HfRJ.js | HTTP 200 | len 420534
  - URL: http://www.powerdot.pt
  - URL: http://www.powerdot.pt</Action>
  - URL: https://api.mapbox.com/geocoding/v5/mapbox.places
  - URL: https://api.mapbox.com/search/searchbox/v1
  - URL: https://api.pwrdt.com
  - URL: https://auth.powerdot.eu/realms
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.pt
  - URL: https://www.powerdot.pt</Action>,
  - Snippet: js","assets/vendor-analytics-pR5Mwgig.js","assets/NeedHelpChoosingChargerPopup-DKH4GCyf.js","assets/ConnectorUnavailablePopup-D2gccAJB.js","assets/_terminal-CwgZ5tJ7.js","assets/UnpaidDebtOverlayManager-BwX9FkjU.js","assets/TutorialPopup-BqDWCees.js","assets/LazyCountryPickerBottomSheet-j
  - Snippet: ew2op.js","assets/vendor-payments-Dn6H7tOa.js","assets/NetworkRatesBottomSheet-CnWikIl2.js","assets/ConnectorsCount-C48C1A3n.js","assets/SectionTitle-D0KDrQOV.js","assets/InlineRateExperience-CPirSG02.js","assets/GetDiscountCodePopup-DkREnbMv.js","assets/useChargingCurveService-CSjfCjAT.j
  - Snippet: CSjfCjAT.js","assets/terminal-charging-CACr3o-a.js","assets/SessionStateBanner-BB3_4Rp0.js","assets/PricingInfoBottomSheet-Di9ACFNL.js","assets/FeatureInfoDrawer-CnM3r4DG.js","assets/subscription-plans-_yQtFhoH.js","assets/SubscriptionPlansBottomSheet-nIXIhVkp.js","assets/_map-auth-BDsr
  - Snippet: ,"assets/session-summary-Bkk-E_yT.js","assets/session-payment-failed-BPscH3QE.js","assets/preparing-connector-Dl-AzDQO.js","assets/pre-authorization-B9r8xpc3.js","assets/ChangeAmountBottomSheet-xa0g9wOr.js","assets/StateBanner-D0kOVRrG.js","assets/payment-D8dFjNU1.js","assets/LazyPaymentE
  - Snippet: Cvtvg7ML.js","assets/location-D6ivoFSD.js","assets/HowToGeoLocationBottomSheet-B-GQE-xo.js","assets/connector-selection-CuEhC9yd.js","assets/coming-soon-Gb4jAkq-.js","assets/charging--g5huhDj.js","assets/subscription-details-pZKQc8xU.js","assets/setup-subscription-C9tRP1Dv.js","assets/Cou
- Asset: https://adhoc.pwrdt.com/assets/index-B36_HfRJ.js | HTTP 200 | len 420534
  - URL: http://www.powerdot.pt
  - URL: http://www.powerdot.pt</Action>
  - URL: https://api.mapbox.com/geocoding/v5/mapbox.places
  - URL: https://api.mapbox.com/search/searchbox/v1
  - URL: https://api.pwrdt.com
  - URL: https://auth.powerdot.eu/realms
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.pt
  - URL: https://www.powerdot.pt</Action>,
  - Snippet: js","assets/vendor-analytics-pR5Mwgig.js","assets/NeedHelpChoosingChargerPopup-DKH4GCyf.js","assets/ConnectorUnavailablePopup-D2gccAJB.js","assets/_terminal-CwgZ5tJ7.js","assets/UnpaidDebtOverlayManager-BwX9FkjU.js","assets/TutorialPopup-BqDWCees.js","assets/LazyCountryPickerBottomSheet-j
  - Snippet: ew2op.js","assets/vendor-payments-Dn6H7tOa.js","assets/NetworkRatesBottomSheet-CnWikIl2.js","assets/ConnectorsCount-C48C1A3n.js","assets/SectionTitle-D0KDrQOV.js","assets/InlineRateExperience-CPirSG02.js","assets/GetDiscountCodePopup-DkREnbMv.js","assets/useChargingCurveService-CSjfCjAT.j
  - Snippet: CSjfCjAT.js","assets/terminal-charging-CACr3o-a.js","assets/SessionStateBanner-BB3_4Rp0.js","assets/PricingInfoBottomSheet-Di9ACFNL.js","assets/FeatureInfoDrawer-CnM3r4DG.js","assets/subscription-plans-_yQtFhoH.js","assets/SubscriptionPlansBottomSheet-nIXIhVkp.js","assets/_map-auth-BDsr
  - Snippet: ,"assets/session-summary-Bkk-E_yT.js","assets/session-payment-failed-BPscH3QE.js","assets/preparing-connector-Dl-AzDQO.js","assets/pre-authorization-B9r8xpc3.js","assets/ChangeAmountBottomSheet-xa0g9wOr.js","assets/StateBanner-D0kOVRrG.js","assets/payment-D8dFjNU1.js","assets/LazyPaymentE
  - Snippet: Cvtvg7ML.js","assets/location-D6ivoFSD.js","assets/HowToGeoLocationBottomSheet-B-GQE-xo.js","assets/connector-selection-CuEhC9yd.js","assets/coming-soon-Gb4jAkq-.js","assets/charging--g5huhDj.js","assets/subscription-details-pZKQc8xU.js","assets/setup-subscription-C9tRP1Dv.js","assets/Cou
