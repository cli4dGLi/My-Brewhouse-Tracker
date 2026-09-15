## Entering data

All routine work happens in this app. The database is storing submitted records in the background.

1. Register material batches with the correct density and extract yield.
2. Register a unique fill ID for each tank campaign.
3. Record opening tank, line and material stock counts at the exact reporting boundary.
4. Log each brew with its actual material quantities and destination fill allocation.
5. Record completed transfers with sent and received volume and gravity. Record GFE dosing separately from the base beer measurement.
6. Log actual packaged output.
7. Record closing stock counts at the reporting boundary.

A fill closure does not replace an empty stock measurement. Zero readings are accepted. Positive stock needs measured gravity. To correct an entry, an administrator voids it with a reason, and the correct replacement is entered.

## Reporting times

Initial shift assumptions are Morning 06:00–14:00, Afternoon 14:00–22:00 and Night 22:00–06:00 next day, in Ghana time. The production day starts at 06:00. Confirm these boundaries before production use.

The week starts Monday. Month and year follow calendar boundaries at 06:00. Movement intervals include the start and exclude the end. A closing stock count at a boundary also supplies the next period's opening.

Current periods remain provisional until closing readings are available. Older readings are not substituted for missing boundary readings.

## Calculations

Measured beer extract equivalent in kg:

~~~text
Extract = volume_hL × (0.9974 / (1 / Plato − 0.00382) + 0.02)
~~~

This preserves the formula used in the attached workbook. Do not apply another multiplier of 10.

Material extract equals quantity × kg per unit × extract yield. Factors are stored with each batch and material use. Concentrate defaults reproduce workbook assumptions and must be checked against the material certificate.

- **Warehouse:** opening extract + receipts − material used − closing extract. Destruction is part of this discrepancy and is not subtracted again.
- **Brewhouse:** raw-material extract used − extract in wort delivered to tanks.
- **Fermentation / storage:** opening + wort received + transfer receipts − transfer dispatches − closing.
- **Clarification / transfer:** sent base-beer extract + separately added GFE extract − measured received extract. This covers completed transfers, direct transfers and line feeds.
- **Bright beer tanks:** opening + measured receipts − dispatches − closing.
- **Packaging:** opening line stock + measured line-feed receipts − actual packaged output − closing line stock.

Receiving gravity must represent the blended product. GFE is added once to the transfer input. Brewhouse wort credits its destination tank automatically. A single transfer entry updates both vessels.

Percentages use summed loss divided by summed stage availability. Percentages are not averaged or added. Negative loss is shown as an apparent gain for investigation. Missing readings produce Incomplete, and No activity is distinct from a measured zero loss.

Different stage denominators mean that an unsupported global loss percentage is not shown.

## Initial targets

Warehouse 1.5%; Brewhouse 2.5%; Fermentation/storage 3%; Clarification/transfer 3%; Bright beer tanks 3%; Packaging 2%.

These reproduce workbook settings. Confirm approved operating targets before use.

## Historical workbook

The attached workbook is the only initial data source. It has not yet been migrated into this rebuilt deployment copy. Audit findings include missing gravities, shifts, fill references and opening/closing readings. Resolve those gaps from actual records or retain their missing status.

The original audit and importer have been recovered, but their integration into this deployment copy still needs validation against independent period totals. Do not upload the workbook into a public source repository. No data from other projects is imported.

## History and backups

All live pages require the configured username and password, including dashboards and logs. Signed-in users can submit entries; an optional logging PIN adds another submission check. A separate administrator PIN protects voiding and complete backups. Use Sign out on shared devices. Entered names are self-reported; the shared application login does not identify individual operators.

Voiding preserves original details and records the reviewer, reason and UTC time. Backup export includes active and voided records from both breweries. Restore requires an empty database.

Record retention has no automatic expiry in this application. Provider recovery and independent scheduled backups still need configuration and verification.

## Current limits

This version records within-site movements. Inter-site transfers, financial waste valuation, individual login roles and automatic historical workbook migration are not yet included. Use a dedicated database or schema for this app.

Reports reflect only records entered or correctly migrated into this app.
