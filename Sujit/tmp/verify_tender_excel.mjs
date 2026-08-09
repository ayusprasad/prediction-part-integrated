import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "C:/Users/kumar/Desktop/project2/Sujit/outputs/tender_workflow_source_pack.xlsx";
const previewPath = "C:/Users/kumar/Desktop/project2/Sujit/tmp/tender_workflow_overview.png";
const blob = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(blob);
const inspection = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 5000,
  tableMaxRows: 5,
  tableMaxCols: 8,
});
console.log(inspection.ndjson);
const preview = await workbook.render({
  sheetName: "Overview",
  range: "A1:D14",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
