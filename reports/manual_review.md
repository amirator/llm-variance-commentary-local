# Manual review of accepted model drafts

I read every draft that the checker accepted as model text (`source == "llm"`) against its fact sheet in `data/factsheets/`. The verdicts are my own reading, not output of the checker; `scripts/build_manual_review.py` holds them as data and renders this page. `scripts/audit_attribution.py` was used only as a lead, and several of the errors below are ones it did not flag.

Verdicts: **OK** everything matches the sheet. **WORD** figures are right but the text adds an evaluative or causal phrase the facts do not support. **FIG** a figure from the sheet is attached to the wrong line item, measure or period. **STMT** a sentence contradicts the sheet (wrong direction, wrong attribution, wrong definition). FIG and STMT are counted as factual errors; WORD is not, but is reported separately. A few calls are borderline and are marked as such.

## Totals

| Model | Accepted drafts | Factual error (FIG + STMT) | of which FIG | of which STMT | WORD only | OK |
|---|---|---|---|---|---|---|
| Qwen2.5-1.5B-Instruct | 30 | **12** | 7 | 5 | 4 | 14 |
| Qwen2.5-0.5B-Instruct | 7 | **7** | 5 | 2 | 0 | 0 |

## Qwen2.5-1.5B-Instruct

| Sheet | Verdict | Note |
|---|---|---|
| `costco_FY2024` | STMT | Calls net income (+17.1%) and operating income (+14.4%) the 'largest revenue and income contributors'; the sheet gives no such contribution measure, they are just two line items that grew. |
| `costco_FY2026` | WORD | Figures correct. 'Strong financial performance ... investment in growth' is interpretation. |
| `lacity_bva_FY2025` | FIG | Unappropriated Balance is given as 'utilisation 100.0%' (that is the unspent share; utilisation is 0.0%). General City Purposes 'utilisation 44.6%' is also the unspent share (utilisation is 55.4%). So the 'lowest utilisation' sentence states the opposite of the data. |
| `lacity_bva_FY2026` | FIG | 'Lowest budget utilisation ... with figures of $397.9m, $263.5m, $89.1m' are the revised budgets of General Services, General City Purposes and Mayor, not utilisation (71.6%, 71.8%, 76.6%). |
| `lacity_gf_2025-07` | OK | Total, drivers and amounts match. |
| `lacity_gf_2025-08` | OK | Total, drivers and amounts match. |
| `lacity_gf_2025-09` | OK | Total, drivers and amounts match. |
| `lacity_gf_2025-10` | STMT | 'This increase is attributed to ... Capital Finance Administration (+$64.3m) and the Fire department, which experienced a decrease of $21.4m.' Fire fell, so it cannot be a source of the increase. |
| `lacity_gf_2025-11` | OK | Total, drivers and amounts match. |
| `lacity_gf_2025-12` | STMT | 'This increase was driven by Non-Departmental - General (+$115.6m) and Fire, which decreased by $9.9m.' Same problem: a decreasing item named as a driver of the increase. |
| `lacity_gf_2026-01` | WORD | Figures correct. 'These figures highlight significant growth in the city's financial operations' is interpretation, and the total only moved +1.6%. |
| `lacity_gf_2026-02` | STMT | 'The decrease is attributed to Human Resources Benefits, which increased by $13.6m ...' The first driver rose, so it did not cause the decrease. |
| `lacity_gf_2026-03` | OK | Total, five movers and amounts match. |
| `lacity_gf_2026-04` | FIG | Liability Claims is given a 7.4% decrease; 7.4% is Non-Departmental General's change, Liability Claims fell 50.3% (the $12.8m is right). |
| `lacity_gf_2026-05` | OK | Total, drivers and amounts match. |
| `lacity_gf_2026-06` | OK | Total, drivers and amounts match. |
| `sama_pos_2021Q3` | WORD | Figures correct. 'Robust performance of the Restaurants & Café sector' is interpretation (borderline). |
| `sama_pos_2021Q4` | OK | Figures and attributions match. |
| `sama_pos_2022Q1` | FIG | Electronic & Electric Devices is given an 'average weekly value of SAR 305 million'; that is the Q1 2021 value, the Q1 2022 value is SAR 268 million. Also 'reflecting a strong performance' (interpretation). |
| `sama_pos_2022Q2` | OK | Figures and attributions match. |
| `sama_pos_2022Q3` | STMT | 'The Other category, which includes miscellaneous goods and services' - the sheet lists them as two separate categories (Other +31.2%, Miscellaneous +38.0%); the figures themselves are right. |
| `sama_pos_2022Q4` | WORD | Figures correct. 'Indicate a strong performance in the retail sector' is interpretation. |
| `sama_pos_2023Q1` | OK | Figures and attributions match. |
| `sama_pos_2023Q4` | OK | Figures and attributions match. |
| `sama_pos_2024Q1` | OK | Figures and attributions match. |
| `sama_pos_2024Q2` | OK | Figures and attributions match. |
| `sama_pos_2024Q3` | FIG | Says the Other category's SAR 221m rise contributed to 'a total increase of 213 million SAR'; 213 is Electronic & Electric Devices' current value. Also 'improvement in the spending habits of consumers' (interpretation). |
| `sama_pos_2024Q4` | OK | Figures and attributions match. |
| `sama_pos_2025Q1` | FIG | 'Other and miscellaneous goods and services ... +20.6%, from SAR 2,056m to SAR 2,480m' - those are Other's figures alone; Miscellaneous Goods and Services rose 9.7%. |
| `sama_pos_2025Q2` | FIG | 'Reached a total of SAR 12.88 billion' - 12.88bn is the average weekly POS value, not a total for the quarter (borderline: the rest of the draft is correct). |

## Qwen2.5-0.5B-Instruct

| Sheet | Verdict | Note |
|---|---|---|
| `costco_FY2024` | FIG | Net income and operating income changes are swapped: net income rose $1.07bn and operating income $1.17bn, the draft says the reverse. |
| `costco_FY2026` | FIG | '$27.9bn, which is a 8.9% increase in operating cash flow from $13.34bn to $15.82bn' - 8.9% is SG&A growth (cash flow grew 18.6%) and $27.9bn is the revenue change. Capex growth is given as 18.6%, which is the cash-flow figure (capex +17.0%). |
| `lacity_gf_2026-03` | FIG | Water and Electricity 'decreased by $4.1m'; the sheet says $4.2m (4.1 is Petroleum Products). |
| `sama_pos_2021Q3` | STMT | Says Miscellaneous Goods and Services had 'a decrease of 4 million SAR' and that the 'increase ... is modest'; it rose SAR 303m, the -SAR 4m belongs to Electronics. Also 'growing steadily over the past year' (no support). |
| `sama_pos_2022Q1` | FIG | 'Other and Miscellaneous Goods and Services experienced an increase of SAR 357m' (357 is Other only); 44.0% is given for Other and 30.9% for Miscellaneous, which are swapped. |
| `sama_pos_2023Q4` | FIG | Beverage and Food and Restaurants & Café 'saw their values increase by 1.07 billion SAR' - that is the total weekly change; Miscellaneous is given 14.1% in one sentence (that is Beverage and Food) and 15.3% in the next. |
| `sama_pos_2024Q4` | STMT | 'Gas Stations (up) ... experienced decreases' and 'Gas Stations (up) and Public Utilities (down) remained unchanged' - Gas Stations rose SAR 127m, Public Utilities fell SAR 67m. |
