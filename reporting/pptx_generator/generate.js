// generate.js
// CLI entry: node generate.js --input data.json --output out.pptx --identity polaris

import { readFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import minimist from "minimist";
import pptxgen from "pptxgenjs";

import { getIdentity, VALID_IDENTITIES } from "./src/identities.js";
import { buildMasters } from "./src/masters.js";

import buildCoverSlide from "./src/slides/cover.js";
import buildExecSummarySlide from "./src/slides/exec_summary.js";
import buildKpiDashboardSlide from "./src/slides/kpi_dashboard.js";
import buildDeepDiveSlide from "./src/slides/deep_dive.js";
import buildComparisonSlide from "./src/slides/comparison.js";
import buildWatchAreasSlide from "./src/slides/watch_areas.js";
import buildRecommendationsSlide from "./src/slides/recommendations.js";
import buildPeerTableSlide from "./src/slides/peer_table.js";
import buildAppendixSlide from "./src/slides/appendix.js";

const SLIDE_BUILDERS = {
  cover: buildCoverSlide,
  exec_summary: buildExecSummarySlide,
  kpi_dashboard: buildKpiDashboardSlide,
  deep_dive: buildDeepDiveSlide,
  comparison: buildComparisonSlide,
  watch_areas: buildWatchAreasSlide,
  recommendations: buildRecommendationsSlide,
  peer_table: buildPeerTableSlide,
  appendix: buildAppendixSlide,
};

async function main() {
  const argv = minimist(process.argv.slice(2));
  const inputPath = argv.input || argv.i;
  const outputPath = argv.output || argv.o;
  const identityName = argv.identity || argv.id || "polaris";

  if (!inputPath || !outputPath) {
    console.error("Usage: node generate.js --input <data.json> --output <out.pptx> [--identity polaris|mckinsey|bcg|bain]");
    console.error(`Valid identities: ${VALID_IDENTITIES.join(", ")}`);
    process.exit(1);
  }

  const data = JSON.parse(readFileSync(resolve(inputPath), "utf-8"));
  const id = getIdentity(identityName);

  console.log(`[generate] Identity: ${id.name}`);
  console.log(`[generate] Input:    ${inputPath}`);
  console.log(`[generate] Output:   ${outputPath}`);
  console.log(`[generate] Sections: ${data.sections?.length || 0}`);

  const pres = new pptxgen();
  pres.author = data.author || "PolarisBI";
  pres.company = "PolarisBI";
  pres.title = data.title || "Untitled Report";
  pres.subject = data.subtitle || "";

  buildMasters(pres, id);

  if (!data.sections || data.sections.length === 0) {
    data.sections = [{ type: "cover" }];
  }

  let pageNum = 1;
  const totalPages = data.sections.length;

  for (const section of data.sections) {
    const builder = SLIDE_BUILDERS[section.type];
    if (!builder) {
      console.warn(`[generate] Unknown slide type: ${section.type}, skipping`);
      continue;
    }
    try {
      await builder(pres, id, {
        ...data,
        ...section,
        pageNum,
        totalPages,
      });
      pageNum++;
    } catch (err) {
      if (err.message.includes("not yet implemented")) {
        console.warn(`[generate] ${section.type}: ${err.message}`);
      } else {
        throw err;
      }
    }
  }

  const outDir = dirname(resolve(outputPath));
  if (!existsSync(outDir)) {
    mkdirSync(outDir, { recursive: true });
  }

  await pres.writeFile({ fileName: resolve(outputPath) });
  console.log(`[generate] ✓ Saved: ${outputPath}`);
}

main().catch(err => {
  console.error("[generate] ERROR:", err);
  process.exit(1);
});
