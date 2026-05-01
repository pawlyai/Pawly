# Cross-Report Analysis: triage
Generated: 2026-04-22 11:02:20

## 📊 Executive Summary

- **Total Cases:** 20
- **Reports Compared:** 4
- **Agreement Rate:** 40.0%
- **Unanimous Pass:** 8 cases
- **Unanimous Fail:** 0 cases
- **Disagreements:** 12 cases
- **Critical Issues (CV > 0.3):** 3

## 🎯 Agreement Matrix

| Case Name | multiturn_triage_report_gemini-20-flash_v1 | multiturn_triage_report_gemini-20-flash_v2 | multiturn_triage_report_gemini-20-flash_v3 | multiturn_triage_report | Status |
|---|---|---|---|---|---|
| margaret_biscuit_single_episode_full_fol... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| david_tank_repeated_vomiting_obstruction... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| david_rex_senior_dog_pancreatitis_warnin... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| jason_lab_thorn_in_paw_busy_parent... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| david_buster_senior_bloody_stool_melena_... | ✅ | ✅ | ✅ | ✅ | Unanimous Pass |
| maya_biscuit_skipped_meal_anxious_owner... | ❌ 0.20 | ❌ 0.20 | ✅ 0.80 | ❌ 0.40 | ⚠️ Disagreement |
| emma_golden_puppy_progressive_limping_ov... | ❌ 0.60 | ✅ 1.00 | ❌ 0.70 | ❌ 0.70 | ⚠️ Disagreement |
| jason_cocker_yeast_ear_infection_busy_pa... | ❌ 0.70 | ✅ 1.00 | ✅ 0.80 | ✅ 0.90 | ⚠️ Disagreement |
| priya_kiwi_ear_mites_to_hematoma_first_t... | ✅ 0.80 | ❌ 0.60 | ❌ 0.60 | ❌ 0.70 | ⚠️ Disagreement |
| sandra_golden_closed_pyometra_experience... | ❌ 0.80 | ❌ 0.70 | ❌ 0.60 | ✅ 0.90 | ⚠️ Disagreement |

## 🔍 Disagreement Deep Dive

### 1. maya_biscuit_skipped_meal_anxious_owner
**Status:** ⚠️ Disagreement (threshold: 0.7)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.20 ❌
- multiturn_triage_report_gemini-20-flash_v2: 0.20 ❌
- multiturn_triage_report_gemini-20-flash_v3: 0.80 ✅
- multiturn_triage_report: 0.40 ❌
- **Mean:** 0.40
- **StdDev:** 0.28
- **CV (Coefficient of Variation):** 0.71
- **Range:** [0.20, 0.80]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (FAIL): The assistant failed to correctly classify the initial scenario as low-risk, instead over-triaging it to an urgent vet visit despite the dog only skip...

- **multiturn_triage_report_gemini-20-flash_v2** (FAIL): The assistant fundamentally failed to correctly classify the user's 'benign concern' (isolated inappetence in a healthy dog) as low-risk, instead issu...

- **multiturn_triage_report_gemini-20-flash_v3** (PASS): The assistant consistently maintained a supportive and empathetic role, effectively de-escalating the owner's anxiety from initial panic to reassuranc...

- **multiturn_triage_report** (FAIL): The assistant failed to correctly classify the initial 'benign concern' as low-risk, instead escalating it to 'RED FLAG ALERT' and 'URGENT' with repea...

**Root Cause Hypothesis:**
🔴 **HIGH VARIANCE** - This case shows significant inconsistency.
Possible causes:
- Evaluator instruction ambiguity
- Model output non-determinism in edge cases
- Different evaluation focus across reports

**Confidence Assessment:**
🔴 Majority says FAIL (3/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 2. emma_golden_puppy_progressive_limping_overexertion
**Status:** ⚠️ Disagreement (threshold: 0.75)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.60 ❌
- multiturn_triage_report_gemini-20-flash_v2: 1.00 ✅
- multiturn_triage_report_gemini-20-flash_v3: 0.70 ❌
- multiturn_triage_report: 0.70 ❌
- **Mean:** 0.75
- **StdDev:** 0.17
- **CV (Coefficient of Variation):** 0.23
- **Range:** [0.60, 1.00]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (FAIL): The assistant demonstrated strong performance in Evaluation Step 3 by providing a comprehensive vet call script with all relevant details from both da...

- **multiturn_triage_report_gemini-20-flash_v2** (PASS): The LLM fully met all evaluation criteria. It adopted the correct veterinary advisor role, asking targeted initial questions and identifying growth pl...

- **multiturn_triage_report_gemini-20-flash_v3** (FAIL): The assistant failed to meet the Expected Outcome of Step 1 by prematurely assessing the Day 1 scenario (intermittent limping after overexertion) as a...

- **multiturn_triage_report** (FAIL): The assistant prematurely assessed the Day 1 scenario, over-escalating intermittent limping to an "Immediate Vet Visit" instead of providing appropria...

**Root Cause Hypothesis:**
🟡 **MODERATE VARIANCE** - Some inconsistency present.
This case may be borderline and sensitive to evaluation criteria interpretation.

**Confidence Assessment:**
🔴 Majority says FAIL (3/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 3. jason_cocker_yeast_ear_infection_busy_parent
**Status:** ⚠️ Disagreement (threshold: 0.75)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.70 ❌
- multiturn_triage_report_gemini-20-flash_v2: 1.00 ✅
- multiturn_triage_report_gemini-20-flash_v3: 0.80 ✅
- multiturn_triage_report: 0.90 ✅
- **Mean:** 0.85
- **StdDev:** 0.13
- **CV (Coefficient of Variation):** 0.15
- **Range:** [0.70, 1.00]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (FAIL): The LLM demonstrated strong initial engagement by asking focused questions and acknowledging time pressure. It accurately identified the likely yeast/...

- **multiturn_triage_report_gemini-20-flash_v2** (PASS): The LLM fully met all evaluation criteria. It initiated engagement by asking 3 focused questions, explained the necessity of information, acknowledged...

- **multiturn_triage_report_gemini-20-flash_v3** (PASS): The LLM effectively engaged the user by asking focused questions and acknowledging time pressure. It accurately identified signs consistent with yeast...

- **multiturn_triage_report** (PASS): The LLM demonstrated excellent initial engagement by asking focused questions, acknowledging time pressure, and guiding the user's examination. It acc...

**Root Cause Hypothesis:**
🟡 **MODERATE VARIANCE** - Some inconsistency present.
This case may be borderline and sensitive to evaluation criteria interpretation.

**Confidence Assessment:**
🟢 Majority says PASS (3/4)
Recommendation: Likely a valid pass, but review minority failures for edge cases.

---

### 4. priya_kiwi_ear_mites_to_hematoma_first_time_owner
**Status:** ⚠️ Disagreement (threshold: 0.75)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.80 ✅
- multiturn_triage_report_gemini-20-flash_v2: 0.60 ❌
- multiturn_triage_report_gemini-20-flash_v3: 0.60 ❌
- multiturn_triage_report: 0.70 ❌
- **Mean:** 0.68
- **StdDev:** 0.10
- **CV (Coefficient of Variation):** 0.14
- **Range:** [0.60, 0.80]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (PASS): The assistant consistently maintained a supportive and educational role, accurately retained all prior details, and expertly guided the user through t...

- **multiturn_triage_report_gemini-20-flash_v2** (FAIL): The assistant demonstrated strong initial engagement, gathered necessary details effectively, and maintained a warm, educational tone throughout. It c...

- **multiturn_triage_report_gemini-20-flash_v3** (FAIL): The assistant excelled in maintaining a warm, educational, and supportive tone, retaining all prior conversation details, providing comprehensive prep...

- **multiturn_triage_report** (FAIL): The assistant maintained a consistently supportive and educational role, accurately reflected and guided the user through the evolving scenario, and r...

**Root Cause Hypothesis:**
🟢 **LOW VARIANCE** - Scores are close but span the threshold.
This is likely a borderline case where small evaluation differences matter.

**Confidence Assessment:**
🔴 Majority says FAIL (3/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 5. sandra_golden_closed_pyometra_experienced_breeder
**Status:** ⚠️ Disagreement (threshold: 0.85)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.80 ❌
- multiturn_triage_report_gemini-20-flash_v2: 0.70 ❌
- multiturn_triage_report_gemini-20-flash_v3: 0.60 ❌
- multiturn_triage_report: 0.90 ✅
- **Mean:** 0.75
- **StdDev:** 0.13
- **CV (Coefficient of Variation):** 0.17
- **Range:** [0.60, 0.90]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (FAIL): The LLM excelled in its role as a proactive veterinary assistant, correctly identifying the emergency (pyometra) based on the initial scenario details...

- **multiturn_triage_report_gemini-20-flash_v2** (FAIL): The LLM correctly identified the emergency, maintained urgency, and effectively navigated owner resistance by explaining closed pyometra risk, outlini...

- **multiturn_triage_report_gemini-20-flash_v3** (FAIL): The assistant failed to fulfill its role as a proactive questioner in Turn 1 by stating Goldie's intact status and last heat cycle as facts that the u...

- **multiturn_triage_report** (PASS): The assistant performed exceptionally well in identifying pyometra as an urgent primary concern based on the user's description of polydipsia/polyuria...

**Root Cause Hypothesis:**
🟡 **MODERATE VARIANCE** - Some inconsistency present.
This case may be borderline and sensitive to evaluation criteria interpretation.

**Confidence Assessment:**
🔴 Majority says FAIL (3/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 6. priya_lab_diabetes_mellitus_first_time_owner
**Status:** ⚠️ Disagreement (threshold: 0.75)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.90 ✅
- multiturn_triage_report_gemini-20-flash_v2: 0.80 ✅
- multiturn_triage_report_gemini-20-flash_v3: 0.70 ❌
- multiturn_triage_report: 0.70 ❌
- **Mean:** 0.78
- **StdDev:** 0.10
- **CV (Coefficient of Variation):** 0.12
- **Range:** [0.70, 0.90]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (PASS): The assistant maintained a consistently warm, empathetic, and supportive tone throughout the conversation, effectively addressing the first-time owner...

- **multiturn_triage_report_gemini-20-flash_v2** (PASS): The assistant maintained a consistently warm, empathetic, and supportive tone, effectively identified the diabetes triad (excessive thirst/urination, ...

- **multiturn_triage_report_gemini-20-flash_v3** (FAIL): The assistant maintained a consistently warm, empathetic, and supportive tone throughout the conversation, effectively identifying the diabetes triad ...

- **multiturn_triage_report** (FAIL): The assistant maintained a consistently warm, empathetic, and supportive tone throughout the conversation, effectively normalizing the owner's anxieti...

**Root Cause Hypothesis:**
🟢 **LOW VARIANCE** - Scores are close but span the threshold.
This is likely a borderline case where small evaluation differences matter.

**Confidence Assessment:**
🔴 Majority says FAIL (2/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 7. sandra_golden_puppy_bloody_diarrhea_parvo_risk
**Status:** ⚠️ Disagreement (threshold: 0.8)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.70 ❌
- multiturn_triage_report_gemini-20-flash_v2: 0.50 ❌
- multiturn_triage_report_gemini-20-flash_v3: 0.70 ❌
- multiturn_triage_report: 0.80 ✅
- **Mean:** 0.68
- **StdDev:** 0.13
- **CV (Coefficient of Variation):** 0.19
- **Range:** [0.50, 0.80]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (FAIL): The assistant successfully triaged the high-stakes scenario by recommending an immediate vet visit to rule out parvovirus, maintained a firm stance ag...

- **multiturn_triage_report_gemini-20-flash_v2** (FAIL): The assistant demonstrated empathy and firmness, correctly identifying key risk factors (age, vaccination status, symptoms) and triaging for a same-da...

- **multiturn_triage_report_gemini-20-flash_v3** (FAIL): The assistant effectively triaged the urgent situation, providing a clear and non-negotiable recommendation for a same-day vet visit, and handled the ...

- **multiturn_triage_report** (PASS): The assistant largely fulfilled the evaluation criteria, demonstrating a knowledgeable, firm, yet empathetic role throughout the high-stakes scenario....

**Root Cause Hypothesis:**
🟡 **MODERATE VARIANCE** - Some inconsistency present.
This case may be borderline and sensitive to evaluation criteria interpretation.

**Confidence Assessment:**
🔴 Majority says FAIL (3/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 8. tom_chester_cavalier_cardiac_cough_resistant_owner
**Status:** ⚠️ Disagreement (threshold: 0.8)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.60 ❌
- multiturn_triage_report_gemini-20-flash_v2: 0.90 ✅
- multiturn_triage_report_gemini-20-flash_v3: 0.90 ✅
- multiturn_triage_report: 0.80 ✅
- **Mean:** 0.80
- **StdDev:** 0.14
- **CV (Coefficient of Variation):** 0.18
- **Range:** [0.60, 0.90]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (FAIL): The assistant failed to adopt the role of a thorough guide in its initial turn by immediately providing a detailed assessment and recommendation witho...

- **multiturn_triage_report_gemini-20-flash_v2** (PASS): The assistant demonstrated a highly proactive and knowledgeable role throughout the conversation. In the initial exchange, it effectively gathered cru...

- **multiturn_triage_report_gemini-20-flash_v3** (PASS): The assistant demonstrated a proactive and knowledgeable role, quickly identifying the potential cardiac cough scenario in the high-risk CKCS breed ba...

- **multiturn_triage_report** (PASS): The assistant failed to ask the specified initial questions (age, breed, cough characteristics) proactively in Evaluation Step 1, instead asking about...

**Root Cause Hypothesis:**
🟡 **MODERATE VARIANCE** - Some inconsistency present.
This case may be borderline and sensitive to evaluation criteria interpretation.

**Confidence Assessment:**
🟢 Majority says PASS (3/4)
Recommendation: Likely a valid pass, but review minority failures for edge cases.

---

### 9. jason_lab_yellow_green_eye_discharge_conjunctivitis
**Status:** ⚠️ Disagreement (threshold: 0.7)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.70 ✅
- multiturn_triage_report_gemini-20-flash_v2: 1.00 ✅
- multiturn_triage_report_gemini-20-flash_v3: 0.50 ❌
- multiturn_triage_report: 0.60 ❌
- **Mean:** 0.70
- **StdDev:** 0.22
- **CV (Coefficient of Variation):** 0.31
- **Range:** [0.50, 1.00]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (PASS): The assistant's initial questions were concise and matched the user's rushed tone, effectively gathering details on discharge duration, color, redness...

- **multiturn_triage_report_gemini-20-flash_v2** (PASS): The assistant fully met all evaluation criteria. It efficiently gathered necessary information with concise, focused questions, aligning with the user...

- **multiturn_triage_report_gemini-20-flash_v3** (FAIL): The assistant completely failed to ask initial focused questions (discharge color, laterality, duration) as required by Evaluation Step 1, instead imm...

- **multiturn_triage_report** (FAIL): The assistant's initial questions were concise but missed asking for discharge color and laterality. While it correctly gathered associated signs and ...

**Root Cause Hypothesis:**
🔴 **HIGH VARIANCE** - This case shows significant inconsistency.
Possible causes:
- Evaluator instruction ambiguity
- Model output non-determinism in edge cases
- Different evaluation focus across reports

**Confidence Assessment:**
🔴 Majority says FAIL (2/4)
Recommendation: Likely a valid failure, investigate why some reports passed.

---

### 10. tom_boxer_progressive_corneal_ulcer_resistance
**Status:** ⚠️ Disagreement (threshold: 0.75)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.50 ❌
- multiturn_triage_report_gemini-20-flash_v2: 0.80 ✅
- multiturn_triage_report_gemini-20-flash_v3: 0.80 ✅
- multiturn_triage_report: 0.90 ✅
- **Mean:** 0.75
- **StdDev:** 0.17
- **CV (Coefficient of Variation):** 0.23
- **Range:** [0.50, 0.90]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (FAIL): The assistant failed to correctly triage the initial presentation of clear unilateral discharge with no pain signs as monitor-at-home, instead immedia...

- **multiturn_triage_report_gemini-20-flash_v2** (PASS): The assistant demonstrated excellent rapport building and correctly triaged the initial mild symptoms as monitor-at-home, avoiding over-triaging. It e...

- **multiturn_triage_report_gemini-20-flash_v3** (PASS): The assistant demonstrated strong rapport building and a non-condescending tone throughout the conversation, effectively navigating the skeptical owne...

- **multiturn_triage_report** (PASS): The assistant largely fulfilled the evaluation criteria. In the initial presentation, it correctly triaged the clear discharge as monitor-at-home and ...

**Root Cause Hypothesis:**
🟡 **MODERATE VARIANCE** - Some inconsistency present.
This case may be borderline and sensitive to evaluation criteria interpretation.

**Confidence Assessment:**
🟢 Majority says PASS (3/4)
Recommendation: Likely a valid pass, but review minority failures for edge cases.

---

### 11. tom_hank_vaccine_reaction_facial_swelling_escalation
**Status:** ⚠️ Disagreement (threshold: 0.75)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 0.80 ✅
- multiturn_triage_report_gemini-20-flash_v2: 0.80 ✅
- multiturn_triage_report_gemini-20-flash_v3: 0.90 ✅
- multiturn_triage_report: 0.70 ❌
- **Mean:** 0.80
- **StdDev:** 0.08
- **CV (Coefficient of Variation):** 0.10
- **Range:** [0.70, 0.90]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (PASS): The assistant demonstrated a knowledgeable and empathetic role throughout the conversation. In the initial response, it asked focused questions, corre...

- **multiturn_triage_report_gemini-20-flash_v2** (PASS): The assistant demonstrated an empathetic and expert role throughout the conversation, correctly classifying initial mild symptoms, providing clear tie...

- **multiturn_triage_report_gemini-20-flash_v3** (PASS): The assistant performed exceptionally well in its initial response (Evaluation Step 1), demonstrating a knowledgeable and empathetic role, asking focu...

- **multiturn_triage_report** (FAIL): The assistant performed well in the initial scenario, correctly classifying mild day-1 symptoms, asking focused questions, and offering proactive foll...

**Root Cause Hypothesis:**
🟢 **LOW VARIANCE** - Scores are close but span the threshold.
This is likely a borderline case where small evaluation differences matter.

**Confidence Assessment:**
🟢 Majority says PASS (3/4)
Recommendation: Likely a valid pass, but review minority failures for edge cases.

---

### 12. maya_biscuit_puppy_mild_diarrhea_new_treats
**Status:** ⚠️ Disagreement (threshold: 0.7)

**Score Distribution:**
- multiturn_triage_report_gemini-20-flash_v1: 1.00 ✅
- multiturn_triage_report_gemini-20-flash_v2: 0.30 ❌
- multiturn_triage_report_gemini-20-flash_v3: 0.90 ✅
- multiturn_triage_report: 0.90 ✅
- **Mean:** 0.78
- **StdDev:** 0.32
- **CV (Coefficient of Variation):** 0.41
- **Range:** [0.30, 1.00]

**Failure Reasons:**
- **multiturn_triage_report_gemini-20-flash_v1** (PASS): The assistant's empathetic and non-dismissive role effectively navigated the anxious scenario, acknowledging distress and asking three focused questio...

- **multiturn_triage_report_gemini-20-flash_v2** (FAIL): The assistant's performance significantly deviates from the evaluation steps, primarily in Step 2. Despite the scenario describing a mild GI upset (si...

- **multiturn_triage_report_gemini-20-flash_v3** (PASS): The assistant's empathetic role effectively navigated the anxious scenario, acknowledging distress and asking focused questions that elicited crucial ...

- **multiturn_triage_report** (PASS): The assistant's empathetic role effectively navigated the anxious scenario by acknowledging distress and asking three focused questions, gathering suf...

**Root Cause Hypothesis:**
🔴 **HIGH VARIANCE** - This case shows significant inconsistency.
Possible causes:
- Evaluator instruction ambiguity
- Model output non-determinism in edge cases
- Different evaluation focus across reports

**Confidence Assessment:**
🟢 Majority says PASS (3/4)
Recommendation: Likely a valid pass, but review minority failures for edge cases.

---

## 📈 Pattern Analysis

### Variance Distribution
- **High Variance (CV > 0.3):** 3 cases - Requires investigation
- **Medium Variance (0.15 < CV ≤ 0.3):** 6 cases - Acceptable but monitor
- **Low Variance (CV ≤ 0.15):** 3 cases - Good consistency

## 🎯 Actionable Insights

### 🔴 Critical (High Variance)
- **maya_biscuit_skipped_meal_anxious_owner**
  - CV: 0.71, Score range: [0.20, 0.80]
  - Action: Manual review required, evaluation criteria may be unclear

- **jason_lab_yellow_green_eye_discharge_conjunctivitis**
  - CV: 0.31, Score range: [0.50, 1.00]
  - Action: Manual review required, evaluation criteria may be unclear

- **maya_biscuit_puppy_mild_diarrhea_new_treats**
  - CV: 0.41, Score range: [0.30, 1.00]
  - Action: Manual review required, evaluation criteria may be unclear

### 🟡 Important (Borderline Cases)
- **emma_golden_puppy_progressive_limping_overexertion**
  - Mean: 0.75, Threshold: 0.75
  - Action: Consider threshold adjustment or model improvement

- **jason_cocker_yeast_ear_infection_busy_parent**
  - Mean: 0.85, Threshold: 0.75
  - Action: Consider threshold adjustment or model improvement

- **priya_kiwi_ear_mites_to_hematoma_first_time_owner**
  - Mean: 0.68, Threshold: 0.75
  - Action: Consider threshold adjustment or model improvement

## 📋 Summary Statistics

**Agreement Rate by Category:**
- Unanimous Pass: 40.0%
- Unanimous Fail: 0.0%
- Disagreement: 60.0%

## 🔬 Data Sources

- multiturn_triage_report_gemini-20-flash_v1
- multiturn_triage_report_gemini-20-flash_v2
- multiturn_triage_report_gemini-20-flash_v3
- multiturn_triage_report

---
*Generated by Pawly Cross-Report Comparator*