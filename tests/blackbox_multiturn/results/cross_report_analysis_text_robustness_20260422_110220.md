# Cross-Report Analysis: text_robustness
Generated: 2026-04-22 11:02:20

## 📊 Executive Summary

- **Total Cases:** 5
- **Reports Compared:** 4
- **Agreement Rate:** 60.0%
- **Unanimous Pass:** 3 cases
- **Unanimous Fail:** 0 cases
- **Disagreements:** 2 cases
- **Critical Issues (CV > 0.3):** 0

## 🎯 Agreement Matrix

| Case Name | multiturn_text_robustness_report_gemini-20-flash_v3 | multiturn_text_robustness_report_gemini-20-flash_v2 | multiturn_text_robustness_report | multiturn_text_robustness_report_gemini-20-flash_v1 | Status |
|---|---|---|---|---|---|
| maya_biscuit_noisy_text_vomiting_intent... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| jason_buddy_colloquial_bloat_like_langua... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| priya_luna_fragmented_text_polyuria_poly... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| emma_poppy_typo_heavy_itchy_ear_intent... | ❌ 0.80 | ✅ 0.90 | ❌ 0.80 | ✅ 0.90 | ⚠️ Disagreement |
| david_rex_messy_text_lameness_vs_neuro_i... | ✅ 0.90 | ❌ 0.60 | ✅ 0.90 | ❌ 0.70 | ⚠️ Disagreement |

## 🔍 Disagreement Deep Dive

### 1. emma_poppy_typo_heavy_itchy_ear_intent
**Status:** ⚠️ Disagreement (threshold: 0.84)

**Score Distribution:**
- multiturn_text_robustness_report_gemini-20-flash_v3: 0.80 ❌
- multiturn_text_robustness_report_gemini-20-flash_v2: 0.90 ✅
- multiturn_text_robustness_report: 0.80 ❌
- multiturn_text_robustness_report_gemini-20-flash_v1: 0.90 ✅
- **Mean:** 0.85
- **StdDev:** 0.06
- **CV (Coefficient of Variation):** 0.07
- **Range:** [0.80, 0.90]

**Failure Reasons:**
- **multiturn_text_robustness_report_gemini-20-flash_v3** (FAIL): The assistant correctly interprets the user's typo-heavy colloquial English to identify an ear irritation or infection, adopting a helpful and underst...

- **multiturn_text_robustness_report_gemini-20-flash_v2** (PASS): The assistant correctly interprets the user's 'typo-heavy colloquial English' to identify 'ear irritation or infection' and adopts a helpful role, ful...

- **multiturn_text_robustness_report** (FAIL): The assistant correctly interprets the user's typo-heavy colloquial English to identify an ear irritation or infection, adopting a helpful and underst...

- **multiturn_text_robustness_report_gemini-20-flash_v1** (PASS): The assistant correctly interpreted the user's typo-heavy colloquial English to identify ear irritation/infection as the primary concern, fulfilling i...

**Root Cause Hypothesis:**
🟢 **LOW VARIANCE** - Scores are close but span the threshold.
This is likely a borderline case where small evaluation differences matter.

**Confidence Assessment:**
🔴 Majority says FAIL (2/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 2. david_rex_messy_text_lameness_vs_neuro_intent
**Status:** ⚠️ Disagreement (threshold: 0.86)

**Score Distribution:**
- multiturn_text_robustness_report_gemini-20-flash_v3: 0.90 ✅
- multiturn_text_robustness_report_gemini-20-flash_v2: 0.60 ❌
- multiturn_text_robustness_report: 0.90 ✅
- multiturn_text_robustness_report_gemini-20-flash_v1: 0.70 ❌
- **Mean:** 0.78
- **StdDev:** 0.15
- **CV (Coefficient of Variation):** 0.19
- **Range:** [0.60, 0.90]

**Failure Reasons:**
- **multiturn_text_robustness_report_gemini-20-flash_v3** (PASS): The LLM consistently identified the scenario as abnormal gait/weakness and effectively acknowledged ambiguity in the initial turns, maintaining a broa...

- **multiturn_text_robustness_report_gemini-20-flash_v2** (FAIL): The LLM successfully identified the scenario as abnormal gait/weakness and handled initial ambiguity in turns 1 and 2, asking relevant clarifying ques...

- **multiturn_text_robustness_report** (PASS): The LLM consistently identified the scenario as abnormal gait/weakness and effectively acknowledged ambiguity in the initial turns, maintaining a broa...

- **multiturn_text_robustness_report_gemini-20-flash_v1** (FAIL): The assistant correctly interprets the initial ambiguous user input, maintaining a broad understanding of gait abnormality and acknowledging ambiguity...

**Root Cause Hypothesis:**
🟡 **MODERATE VARIANCE** - Some inconsistency present.
This case may be borderline and sensitive to evaluation criteria interpretation.

**Confidence Assessment:**
🔴 Majority says FAIL (2/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

## 📈 Pattern Analysis

### Variance Distribution
- **High Variance (CV > 0.3):** 0 cases - Requires investigation
- **Medium Variance (0.15 < CV ≤ 0.3):** 1 cases - Acceptable but monitor
- **Low Variance (CV ≤ 0.15):** 1 cases - Good consistency

## 🎯 Actionable Insights

### 🟡 Important (Borderline Cases)
- **emma_poppy_typo_heavy_itchy_ear_intent**
  - Mean: 0.85, Threshold: 0.84
  - Action: Consider threshold adjustment or model improvement

- **david_rex_messy_text_lameness_vs_neuro_intent**
  - Mean: 0.78, Threshold: 0.86
  - Action: Consider threshold adjustment or model improvement

## 📋 Summary Statistics

**Agreement Rate by Category:**
- Unanimous Pass: 60.0%
- Unanimous Fail: 0.0%
- Disagreement: 40.0%

## 🔬 Data Sources

- multiturn_text_robustness_report_gemini-20-flash_v3
- multiturn_text_robustness_report_gemini-20-flash_v2
- multiturn_text_robustness_report
- multiturn_text_robustness_report_gemini-20-flash_v1

---
*Generated by Pawly Cross-Report Comparator*