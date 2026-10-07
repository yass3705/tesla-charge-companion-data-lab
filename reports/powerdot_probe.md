# Powerdot direct QR probe v2

- Powerdot IRVE rows: **7733**
- Unique stations: **1181**
- EVSE/PDC: **7733**
- Stations with IRVE tarification text: **1**
- QR probes: **202**
- QR HTTP 200: **4**
- Derived QR HTTP 200: **2**

## Known public QR probes

- Mr Bricolage Champniers | MRB_CHP_KPC20001 | HTTP 200 | len 3696 | final https://adhoc.pwrdt.com/?charger_name=MRB_CHP_KPC20001
- Netto Soustons | NET_SST_KPS20001 | HTTP 200 | len 3696 | final https://adhoc.pwrdt.com/?charger_name=NET_SST_KPS20001

## Successful derived QR candidates

- ACE Hôtel Paris - Sud Villabé | ACE_VIL_SLM10001 | https://adhoc.pwrdt.com/?charger_name=ACE_VIL_SLM10001
- Action - Verneuil d'Avre | ACT_VDD_KPS20001 | https://adhoc.pwrdt.com/connector-selection?charger_name=ACT_VDD_KPS20001

## Frontend/API findings

- Asset: https://adhoc.pwrdt.com/assets/index-DjLGPfWV.js | HTTP 200 | len 159325
  - URL: http://www.powerdot.es
  - URL: http://www.powerdot.es</Action>
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.es
  - URL: https://www.powerdot.es</Action>
  - Snippet:  EVen ohiko jokabideagatik.",h="Saioaren datuak kargatzen...",c={energy:"Energia",power:"Potentzia",price:"Prezioa",time:"Saioaren denbora",battery:"Bateria"},m="Xehetasunak ikusi",f={graph:{title:"Kargatzeko kurba"},title:"Saioaren xehetasunak"},E="Eskuratu saio-esteka zure posta ele
  - Snippet: a kobratuko da.",title:"Ziur zaude zure saioa gelditu nahi duzula?"},S={overtime:{info:'Saioaren $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minu
  - Snippet: {overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOve
  - Snippet: n.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Apartek
  - Snippet: g>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Aparteko karguak <strong>{{overtimePriceRate}} {{currency}}/min</strong> aplikatuko dira orduan.',runn
- Asset: https://adhoc.pwrdt.com/assets/index-DjLGPfWV.js | HTTP 200 | len 159325
  - URL: http://www.powerdot.es
  - URL: http://www.powerdot.es</Action>
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.es
  - URL: https://www.powerdot.es</Action>
  - Snippet:  EVen ohiko jokabideagatik.",h="Saioaren datuak kargatzen...",c={energy:"Energia",power:"Potentzia",price:"Prezioa",time:"Saioaren denbora",battery:"Bateria"},m="Xehetasunak ikusi",f={graph:{title:"Kargatzeko kurba"},title:"Saioaren xehetasunak"},E="Eskuratu saio-esteka zure posta ele
  - Snippet: a kobratuko da.",title:"Ziur zaude zure saioa gelditu nahi duzula?"},S={overtime:{info:'Saioaren $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minu
  - Snippet: {overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOve
  - Snippet: n.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Apartek
  - Snippet: g>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Aparteko karguak <strong>{{overtimePriceRate}} {{currency}}/min</strong> aplikatuko dira orduan.',runn
- Asset: https://adhoc.pwrdt.com/assets/index-DjLGPfWV.js | HTTP 200 | len 159325
  - URL: http://www.powerdot.es
  - URL: http://www.powerdot.es</Action>
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.es
  - URL: https://www.powerdot.es</Action>
  - Snippet:  EVen ohiko jokabideagatik.",h="Saioaren datuak kargatzen...",c={energy:"Energia",power:"Potentzia",price:"Prezioa",time:"Saioaren denbora",battery:"Bateria"},m="Xehetasunak ikusi",f={graph:{title:"Kargatzeko kurba"},title:"Saioaren xehetasunak"},E="Eskuratu saio-esteka zure posta ele
  - Snippet: a kobratuko da.",title:"Ziur zaude zure saioa gelditu nahi duzula?"},S={overtime:{info:'Saioaren $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minu
  - Snippet: {overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOve
  - Snippet: n.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Apartek
  - Snippet: g>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Aparteko karguak <strong>{{overtimePriceRate}} {{currency}}/min</strong> aplikatuko dira orduan.',runn
- Asset: https://adhoc.pwrdt.com/assets/index-DjLGPfWV.js | HTTP 200 | len 159325
  - URL: http://www.powerdot.es
  - URL: http://www.powerdot.es</Action>
  - URL: https://powerdot.eu/
  - URL: https://powerdot.eu/</Action>,
  - URL: https://www.powerdot.es
  - URL: https://www.powerdot.es</Action>
  - Snippet:  EVen ohiko jokabideagatik.",h="Saioaren datuak kargatzen...",c={energy:"Energia",power:"Potentzia",price:"Prezioa",time:"Saioaren denbora",battery:"Bateria"},m="Xehetasunak ikusi",f={graph:{title:"Kargatzeko kurba"},title:"Saioaren xehetasunak"},E="Eskuratu saio-esteka zure posta ele
  - Snippet: a kobratuko da.",title:"Ziur zaude zure saioa gelditu nahi duzula?"},S={overtime:{info:'Saioaren $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minu
  - Snippet: {overtimeLimitMinutes}} }) minutu igaro ondoren, aparteko karguak aplikatuko dira <strong>{{overtimePriceRate}} {{currency}}/min.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOve
  - Snippet: n.</strong>',minutes_one:"{{count}} minutu",minutes_other:"{{count}} minutuak",reaching:'<strong>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Apartek
  - Snippet: g>$t(tariffBanner.overtime.minutes, {"count": {{minutesUntilOvertime}} })</strong> minutu barru, $t(tariffBanner.overtime.minutes, {"count": {{overtimeLimitMinutes}} }) iritsiko zara. Aparteko karguak <strong>{{overtimePriceRate}} {{currency}}/min</strong> aplikatuko dira orduan.',runn
