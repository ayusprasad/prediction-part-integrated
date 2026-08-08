# Tax Calculation Formulas
## A Step-by-Step Expanded Guide

This document breaks down each tax formula into simple, easy-to-understand steps. Every variable is explained, and each calculation is shown with a clear logical flow.

---

## 1. Tax Categories

Taxes are divided into two main groups based on when they are billed:

### A. Pre Taxes (Billed in **April** and **October**)

| Tax | Description |
|-----|-------------|
| **Property Tax (PT)** | Tax on the property/structure |
| **Water Benefit Tax (WBT)** | Tax for water supply benefits |
| **Sewerage Benefit Tax (SBT)** | Tax for sewerage system benefits |
| **Employee Guarantee Cess (EGCESS)** | Cess for employee guarantees |
| **Street Tax** | Tax for street maintenance |

### B. Post Taxes (Billed in **September** and **March**)

| Tax | Description |
|-----|-------------|
| **Maharashtra Education Cess (MECESS)** | Cess for education funding |
| **Tree Cess** | Cess for tree plantation/environment |

### Billing Schedule Summary

| Tax Type | Billing Month | Applicable Period |
|----------|---------------|-------------------|
| Pre Taxes | April | April – September |
| Pre Taxes | October | October – March |
| Post Taxes | September | April – September |
| Post Taxes | March | October – March |

---

## 2. Base Calculations (Step-by-Step)

Before calculating any tax, you must first compute these six base values **in the exact order shown below**. Think of these as the **building blocks** of all tax formulas.

---

### Step 1: Annual Amount (AM)

This is the total yearly rent and charges. It is simply your monthly total multiplied by 12.

**Formula:**

```
AM = (Rent + Additional Rent + Service Charges + 7A(iii)) × 12
```

**In plain words:** Add up everything the tenant pays per month, then multiply by 12 to get the yearly figure.

---

### Step 2: Letting Value (LV)

This adds one-third (33.33%) to the Annual Amount to account for the property's letting potential.

**Formula:**

```
LV = AM + (AM ÷ 3)
```

**Expanded:**

```
LV = AM × 1.3333
```

**In plain words:** Take the Annual Amount and add one-third of it on top. This gives the estimated letting value of the property.

---

### Step 3: Gross Rateable Value – Property (GRVP)

This deducts a statutory allowance from the Letting Value to arrive at the gross rateable value for the property.

**Formula:**

```
GRVP = LV − ((LV × 9/10) × 9/10)
```

**Let's break this down:**

```
Step 3a: Calculate LV × 9/10  (= 90% of LV)
Step 3b: Take the result from Step 3a and again multiply by 9/10
Step 3c: Subtract this final amount from LV
Result: GRVP
```

**In plain words:** You apply two successive 10% deductions (i.e., take 90% twice) on the Letting Value, then subtract that from LV. This is a statutory reduction.

---

### Step 4: Net Rateable Value – Property (NRVP)

This applies a further 10% deduction to the GRVP to get the net rateable value for property tax purposes.

**Formula:**

```
NRVP = GRVP − (GRVP ÷ 10)
```

**Expanded:**

```
NRVP = GRVP × 0.90
```

**In plain words:** Deduct 10% from GRVP. Whatever remains is NRVP.

---

### Step 5: Gross Rateable Value – Structure (GRVS)

This calculates the rateable value specifically for the structure (building) by removing the Annual Amount from GRVP.

**Formula:**

```
GRVS = GRVP − AM
```

**In plain words:** Subtract the Annual Amount from the Gross Rateable Value of the Property. This isolates the structure's value.

---

### Step 6: Net Rateable Value – Structure (NRVS)

This applies a 10% deduction to GRVS to get the net rateable value for the structure.

**Formula:**

```
NRVS = GRVS − (GRVS ÷ 10)
```

**Expanded:**

```
NRVS = GRVS × 0.90
```

**In plain words:** Deduct 10% from GRVS. Whatever remains is NRVS.

---

### Important Constants to Remember

| Constant | Value | When to Use |
|----------|-------|-------------|
| **NRV Constant Factor** | **0.837** | For **MbPT structures** (structures built by Mumbai Port Trust) |
| **NRV Constant Factor** | **0.792** | For **all other structures** |
| **General Tax Rate** | From master records | Fetch from system |
| **Street Tax Rate** | From master records | Fetch from system |
| **Sewage Tax Rate** | From master records | Fetch from system |
| **Water Tax Rate** | From master records | Fetch from system |

> **Note:** SBT and WBT cesses are **different** from the standard sewage tax rate and general water tax rate.

---

## 3. Individual Tax Formulas (Fully Expanded)

Each tax below is calculated for a **6-month period** (half-yearly). The formulas use the base values (AM, NRVS, NRVP) computed earlier.

---

### Maharashtra Education Cess (MECESS)

**Billed in:** September (for Apr–Sep) and March (for Oct–Mar)

**Original Formula:**

```
(((AM/2) × 0.837 OR 0.792) × MECESS%) + ((NRVS/2) × MECESS%)
```

**Expanded / Step-by-Step:**

```
Part A – Based on Annual Amount:
  1. Divide AM by 2 → (AM ÷ 2)  [half-yearly amount]
  2. Multiply by NRV Constant (0.837 for MbPT, 0.792 for others)
  3. Multiply by MECESS percentage

Part B – Based on Net Rateable Value of Structure:
  1. Divide NRVS by 2 → (NRVS ÷ 2)  [half-yearly NRVS]
  2. Multiply by MECESS percentage

Total MECESS = Part A + Part B
```

**What this means:** This cess has two components: one linked to the annual rent (after applying the NRV constant) and one linked to the structure's net rateable value. Both are halved because the tax is half-yearly.

> **Note:** Use 0.837 for MbPT-built structures and 0.792 for all other structures.

---

### Tree Cess

**Billed in:** September (for Apr–Sep) and March (for Oct–Mar)

**Original Formula:**

```
(((AM/2) × 0.837 OR 0.792) × TREECESS%) + ((NRVS/2) × TREECESS%)
```

**Expanded / Step-by-Step:**

```
Part A – Based on Annual Amount:
  1. Divide AM by 2 → (AM ÷ 2)
  2. Multiply by NRV Constant (0.837 for MbPT, 0.792 for others)
  3. Multiply by Tree Cess percentage

Part B – Based on Net Rateable Value of Structure:
  1. Divide NRVS by 2 → (NRVS ÷ 2)
  2. Multiply by Tree Cess percentage

Total Tree Cess = Part A + Part B
```

**What this means:** Identical structure to MECESS, but using the Tree Cess percentage rate instead. Again, two components are summed for the half-yearly total.

> **Note:** Use 0.837 for MbPT-built structures and 0.792 for all other structures.

---

### Property Tax (PT)

**Billed in:** April (for Apr–Sep) and October (for Oct–Mar)

**Original Formula:**

```
(NRVS × General Tax Rate)/2 + (NRVP × Sewerage Tax Rate)/2 + (NRVP × Water Tax Rate)/2
```

**Expanded / Step-by-Step:**

```
Component 1 – General Property Tax:
  1. Take NRVS (Net Rateable Value of Structure)
  2. Multiply by General Tax Rate
  3. Divide by 2 (half-yearly)

Component 2 – Sewerage Tax:
  1. Take NRVP (Net Rateable Value of Property)
  2. Multiply by Sewerage Tax Rate
  3. Divide by 2 (half-yearly)

Component 3 – Water Tax:
  1. Take NRVP (Net Rateable Value of Property)
  2. Multiply by Water Tax Rate
  3. Divide by 2 (half-yearly)

Total Property Tax = Component 1 + Component 2 + Component 3
```

**What this means:** Property Tax is a combination of three sub-taxes: general tax on the structure, sewerage tax on the property, and water tax on the property. Each is halved for the 6-month period.

> **Note:** If the tenant is separately charged for water consumption, the water tax component is **NOT** included in Property Tax calculation.

---

### Water Benefit Tax (WBT)

**Billed in:** April (for Apr–Sep) and October (for Oct–Mar)

**Original Formula:**

```
(((AM/2) × 0.837 OR 0.792) × WBT%) + ((NRVS/2) × WBT%)
```

**Expanded / Step-by-Step:**

```
Part A – Based on Annual Amount:
  1. Divide AM by 2 → (AM ÷ 2)
  2. Multiply by NRV Constant (0.837 for MbPT, 0.792 for others)
  3. Multiply by WBT percentage

Part B – Based on Net Rateable Value of Structure:
  1. Divide NRVS by 2 → (NRVS ÷ 2)
  2. Multiply by WBT percentage

Total WBT = Part A + Part B
```

**What this means:** Water Benefit Tax follows the same dual-component pattern: one part tied to annual rent (with NRV constant) and one tied to the structure's net rateable value. Both are half-yearly.

> **Note:** WBT percentage is **different** from the general water tax rate. Fetch WBT% from master records.

---

### Sewerage Benefit Tax (SBT)

**Billed in:** April (for Apr–Sep) and October (for Oct–Mar)

**Original Formula:**

```
(((AM/2) × 0.837 OR 0.792) × SBT%) + ((NRVS/2) × SBT%)
```

**Expanded / Step-by-Step:**

```
Part A – Based on Annual Amount:
  1. Divide AM by 2 → (AM ÷ 2)
  2. Multiply by NRV Constant (0.837 for MbPT, 0.792 for others)
  3. Multiply by SBT percentage

Part B – Based on Net Rateable Value of Structure:
  1. Divide NRVS by 2 → (NRVS ÷ 2)
  2. Multiply by SBT percentage

Total SBT = Part A + Part B
```

**What this means:** Sewerage Benefit Tax follows the same dual-component pattern as WBT, but uses the SBT percentage rate.

> **Note:** SBT percentage is **different** from the general sewage tax rate. Fetch SBT% from master records.

---

### Employee Guarantee Cess (EGCESS)

**Billed in:** April (for Apr–Sep) and October (for Oct–Mar)

**Original Formula:**

```
(((AM/2) × 0.837 OR 0.792) × EGCESS%) + ((NRVS/2) × EGCESS%)
```

**Expanded / Step-by-Step:**

```
Part A – Based on Annual Amount:
  1. Divide AM by 2 → (AM ÷ 2)
  2. Multiply by NRV Constant (0.837 for MbPT, 0.792 for others)
  3. Multiply by EGCESS percentage

Part B – Based on Net Rateable Value of Structure:
  1. Divide NRVS by 2 → (NRVS ÷ 2)
  2. Multiply by EGCESS percentage

Total EGCESS = Part A + Part B
```

**What this means:** Employee Guarantee Cess also uses the dual-component model, with the EGCESS percentage applied to both the adjusted annual amount and the half-yearly NRVS.

> **Note:** Use 0.837 for MbPT-built structures and 0.792 for all other structures.

---

### Street Tax

**Billed in:** April (for Apr–Sep) and October (for Oct–Mar)

**Original Formula:**

```
(NRVP × Street Tax%) / 2
```

**Expanded / Step-by-Step:**

```
Step 1: Take NRVP (Net Rateable Value of Property)
Step 2: Multiply by Street Tax percentage
Step 3: Divide by 2 (half-yearly)

Total Street Tax = (NRVP × Street Tax%) ÷ 2
```

**What this means:** Street Tax is the simplest of all taxes. It is directly proportional to the Net Rateable Value of the Property (NRVP) and is halved for the 6-month billing period.

> **Note:** Street Tax Rate must be fetched from master records.

---

## 4. Quick Reference Summary

Use this table as a quick lookup for any tax formula.

| Tax | Formula (Half-Yearly) | Billed In |
|-----|----------------------|-----------|
| **MECESS** | `((AM/2)×Const)×MECESS% + (NRVS/2)×MECESS%` | Sep, Mar |
| **Tree Cess** | `((AM/2)×Const)×TREE% + (NRVS/2)×TREE%` | Sep, Mar |
| **Property Tax** | `(NRVS×GT%)/2 + (NRVP×ST%)/2 + (NRVP×WT%)/2` | Apr, Oct |
| **WBT** | `((AM/2)×Const)×WBT% + (NRVS/2)×WBT%` | Apr, Oct |
| **SBT** | `((AM/2)×Const)×SBT% + (NRVS/2)×SBT%` | Apr, Oct |
| **EGCESS** | `((AM/2)×Const)×EGC% + (NRVS/2)×EGC%` | Apr, Oct |
| **Street Tax** | `(NRVP × Street%) / 2` | Apr, Oct |

### Abbreviations Used

| Abbreviation | Full Form |
|--------------|-----------|
| AM | Annual Amount |
| LV | Letting Value |
| GRVP | Gross Rateable Value – Property |
| NRVP | Net Rateable Value – Property |
| GRVS | Gross Rateable Value – Structure |
| NRVS | Net Rateable Value – Structure |
| Const | NRV Constant (0.837 or 0.792) |
| GT% | General Tax Rate |
| ST% | Sewerage Tax Rate |
| WT% | Water Tax Rate |

---

## 5. Worked Numerical Example

Let's walk through a complete example with sample numbers to see how everything fits together.

### Assumed Monthly Values

| Item | Amount (₹) |
|------|------------|
| Rent | 10,000 |
| Additional Rent | 2,000 |
| Service Charges | 1,500 |
| 7A(iii) | 500 |
| **Monthly Total** | **14,000** |

### Assumed Tax Rates

| Rate | Value |
|------|-------|
| General Tax Rate | 15% |
| Sewerage Tax Rate | 8% |
| Water Tax Rate | 6% |
| Street Tax Rate | 2% |
| MECESS% | 2% |
| Tree Cess% | 1% |
| WBT% | 3% |
| SBT% | 2% |
| EGCESS% | 1% |
| NRV Constant | 0.837 (MbPT structure) |

### Step-by-Step Calculation

**Step 1 – Annual Amount (AM):**
```
AM = 14,000 × 12 = ₹1,68,000
```

**Step 2 – Letting Value (LV):**
```
LV = AM + (AM ÷ 3) = 1,68,000 + 56,000 = ₹2,24,000
```

**Step 3 – GRVP:**
```
LV × 9/10 = 2,24,000 × 0.9 = 2,01,600
2,01,600 × 9/10 = 1,81,440
GRVP = 2,24,000 − 1,81,440 = ₹42,560
```

**Step 4 – NRVP:**
```
NRVP = GRVP − (GRVP ÷ 10) = 42,560 − 4,256 = ₹38,304
```

**Step 5 – GRVS:**
```
GRVS = GRVP − AM = 42,560 − 1,68,000 = −₹1,25,440
```
> *(Note: Negative value indicates the structure value is less than annual amount after deductions)*

**Step 6 – NRVS:**
```
NRVS = GRVS − (GRVS ÷ 10) = −1,25,440 − (−12,544) = −₹1,12,896
```

---

### Half-Yearly Tax Calculations (April–September)

**Property Tax (PT):**
```
= (NRVS × 15%) / 2 + (NRVP × 8%) / 2 + (NRVP × 6%) / 2
= (−1,12,896 × 0.15) / 2 + (38,304 × 0.08) / 2 + (38,304 × 0.06) / 2
= −8,467.20 + 1,532.16 + 1,149.12 = −₹5,785.92
```

**Water Benefit Tax (WBT):**
```
= ((AM/2) × 0.837 × 3%) + ((NRVS/2) × 3%)
= (84,000 × 0.837 × 0.03) + (−56,448 × 0.03)
= 2,109.24 + (−1,693.44) = ₹415.80
```

**Sewerage Benefit Tax (SBT):**
```
= ((AM/2) × 0.837 × 2%) + ((NRVS/2) × 2%)
= (84,000 × 0.837 × 0.02) + (−56,448 × 0.02)
= 1,406.16 + (−1,128.96) = ₹277.20
```

**Employee Guarantee Cess (EGCESS):**
```
= ((AM/2) × 0.837 × 1%) + ((NRVS/2) × 1%)
= (84,000 × 0.837 × 0.01) + (−56,448 × 0.01)
= 703.08 + (−564.48) = ₹138.60
```

**Street Tax:**
```
= (NRVP × 2%) / 2 = (38,304 × 0.02) / 2 = ₹383.04
```

**MECESS (billed in September):**
```
= ((AM/2) × 0.837 × 2%) + ((NRVS/2) × 2%)
= (84,000 × 0.837 × 0.02) + (−56,448 × 0.02)
= 1,406.16 + (−1,128.96) = ₹277.20
```

**Tree Cess (billed in September):**
```
= ((AM/2) × 0.837 × 1%) + ((NRVS/2) × 1%)
= (84,000 × 0.837 × 0.01) + (−56,448 × 0.01)
= 703.08 + (−564.48) = ₹138.60
```

---

## 6. Important Notes from Original Document

- Property Tax is charged only if a structure has been constructed on the plot by MbPT.
- Prior to 01-10-1982, Property Tax was applicable to all tenancies. From 01-10-1982 onwards, it applies only to MbPT structures.
- If the tenant is separately charged for water consumption, the water tax component is excluded from Property Tax calculation.
- NRV Constant Factor = 0.837 for MbPT structures and 0.792 for all other structures.
- General Tax Rate, Street Tax Rate, Sewage Tax Rate, and Water Tax Rate must be fetched from master records.
- SBT and WBT cesses are different from the standard sewage tax rate and general water tax rate.
