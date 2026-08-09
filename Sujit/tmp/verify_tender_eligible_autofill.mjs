import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "C:/Users/kumar/Desktop/project2/Sujit/outputs/tender_eligible_plot_autofill.xlsx";
const previewPath = "C:/Users/kumar/Desktop/project2/Sujit/tmp/tender_eligible_preview.png";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const check = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 2200,
  tableMaxRows: 4,
  tableMaxCols: 11,
});
console.log(check.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 20 },
  summary: "formula-error scan",
});
console.log(errors.ndjson);
const preview = await workbook.render({
  sheetName: "Eligible Vacant Plots",
  range: "A1:K12",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
