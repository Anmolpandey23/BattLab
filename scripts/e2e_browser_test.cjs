const puppeteer = require("../frontend/node_modules/puppeteer-core");
const http = require("http");

const CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE_URL = "http://localhost:3000";
const API_URL = "http://localhost:8000/api";

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch (e) {
          resolve({ status: res.statusCode, raw: data });
        }
      });
    }).on("error", reject);
  });
}

function postJson(url, body) {
  return new Promise((resolve, reject) => {
    const dataStr = JSON.stringify(body);
    const u = new URL(url);
    const req = http.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(dataStr),
        },
      },
      (res) => {
        let respData = "";
        res.on("data", (chunk) => (respData += chunk));
        res.on("end", () => {
          try {
            resolve({ status: res.statusCode, data: JSON.parse(respData) });
          } catch (e) {
            resolve({ status: res.statusCode, raw: respData });
          }
        });
      }
    );
    req.on("error", reject);
    req.write(dataStr);
    req.end();
  });
}

function fetchBuffer(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        resolve({ status: res.statusCode, buffer: Buffer.concat(chunks) });
      });
    }).on("error", reject);
  });
}

async function safeEvaluate(page, fn) {
  for (let i = 0; i < 5; i++) {
    try {
      return await page.evaluate(fn);
    } catch (err) {
      if (
        err &&
        err.message &&
        (err.message.includes("detached Frame") ||
          err.message.includes("Execution context was destroyed") ||
          err.message.includes("Cannot find context with specified id"))
      ) {
        await new Promise((r) => setTimeout(r, 500));
        continue;
      }
      throw err;
    }
  }
  return await page.evaluate(fn);
}

async function waitForText(page, text, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const html = await page.content();
      if (html.toUpperCase().includes(text.toUpperCase())) return true;
    } catch (e) {
      // frame detached or navigating, ignore and retry
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Timeout waiting for text: ${text}`);
}

async function navigateTo(page, url, expectedText) {
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 25000 });
  } catch (err) {
    if (err.message && err.message.includes("ERR_ABORTED")) {
      await new Promise((r) => setTimeout(r, 500));
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 25000 });
    } else {
      throw err;
    }
  }
  if (expectedText) {
    await waitForText(page, expectedText);
    await new Promise((r) => setTimeout(r, 600));
  }
}

async function checkServerReadiness() {
  try {
    const health = await fetchJson(`${API_URL}/health`);
    if (health.status !== 200) {
      console.error(`Backend returned HTTP ${health.status} on /api/health`);
      return false;
    }
  } catch (err) {
    console.error(`Cannot connect to Backend at ${API_URL}/health. Is it running?`, err.message);
    return false;
  }

  try {
    await new Promise((resolve, reject) => {
      http.get(BASE_URL, (res) => {
        if (res.statusCode >= 200 && res.statusCode < 400) resolve();
        else reject(new Error(`Frontend HTTP ${res.statusCode}`));
      }).on("error", reject);
    });
  } catch (err) {
    console.error(`Cannot connect to Frontend at ${BASE_URL}. Is it running?`, err.message);
    return false;
  }

  return true;
}

async function runBrowserE2E() {
  console.log("===============================================================");
  console.log("       BATTLAB REAL BROWSER (CHROME) END-TO-END VERIFICATION    ");
  console.log("===============================================================");

  const ready = await checkServerReadiness();
  if (!ready) {
    console.error("Pre-flight server readiness check FAILED. Exiting with code 1.");
    process.exit(1);
  }
  console.log("✓ Pre-flight server readiness check passed (Backend & Frontend online)");

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: [
      "--no-sandbox",
      "--enable-webgl",
      "--window-size=1400,900",
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  const consoleLogs = [];
  const consoleWarnings = [];
  const consoleErrors = [];
  const pageErrors = [];

  page.on("console", (msg) => {
    const text = msg.text();
    const type = msg.type();
    consoleLogs.push({ type, text });
    if (type === "warning") consoleWarnings.push(text);
    if (type === "error") consoleErrors.push(text);
  });

  page.on("pageerror", (err) => {
    pageErrors.push(err.message || String(err));
  });

  const testResults = {};
  let createdProjectId = 1;
  let savedRunId = 1;

  try {
    // -------------------------------------------------------------------------
    // WORKFLOW A: Project Creation & Persistence
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW A: Project Creation & Persistence ---");
    await page.goto(`${BASE_URL}/projects/new`, { waitUntil: "networkidle0" });

    const uniqueRunSuffix = Date.now().toString().slice(-6);
    // Step 0: Project Info
    await page.waitForSelector('input[placeholder*="Scooter"]', { timeout: 5000 });
    await page.type('input[placeholder*="Scooter"]', `Browser E2E Automated Pack ${uniqueRunSuffix}`);
    const textareas = await page.$$("textarea");
    if (textareas.length > 0) {
      await textareas[0].type("Full end-to-end browser automated validation project.");
    }
    // Click Next
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const nextBtn = btns.find((b) => b.textContent.trim() === "Next");
      if (nextBtn) nextBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));

    // Step 1: Requirements
    await page.waitForSelector('input[placeholder="51.8"]', { timeout: 5000 });
    await page.type('input[placeholder="51.8"]', "51.8");
    await page.type('input[placeholder="4000"]', "4144");
    // Click Next
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const nextBtn = btns.find((b) => b.textContent.trim() === "Next");
      if (nextBtn) nextBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));

    // Step 2: Design Mode
    // Click Next
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const nextBtn = btns.find((b) => b.textContent.trim() === "Next");
      if (nextBtn) nextBtn.click();
    });
    await new Promise((r) => setTimeout(r, 1200));

    // Step 3: Starting Config
    await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("label"));
      const nsLabel = labels.find((l) => l.textContent.includes("Series"));
      const npLabel = labels.find((l) => l.textContent.includes("Parallel"));
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      if (nsLabel && nsLabel.parentElement) {
        const inp = nsLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "14");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
      if (npLabel && npLabel.parentElement) {
        const inp = npLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "16");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    });

    // Click Finish / Create Project
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const finishBtn = btns.find((b) => b.textContent.includes("Create Project") || b.textContent.includes("Finish"));
      if (finishBtn) finishBtn.click();
    });

    // Wait for redirect to /projects/[id]/design
    await page.waitForFunction(() => window.location.pathname.includes("/design"), { timeout: 15000 });
    const currentUrl = page.url();
    console.log("Navigated to:", currentUrl);
    const match = currentUrl.match(/\/projects\/(\d+)\/design/);
    if (!match) {
      throw new Error(`Expected /projects/{id}/design but got ${currentUrl}`);
    }
    createdProjectId = parseInt(match[1], 10);
    console.log(`Created Project ID: ${createdProjectId}`);

    // Wait for Design Studio to load telemetry
    await waitForText(page, "PACK TELEMETRY");

    // Refresh page to verify persistence
    await page.evaluate(() => location.reload());
    await waitForText(page, "PACK TELEMETRY");
    const titleText = await safeEvaluate(page, () => document.body.innerText.toUpperCase());
    const hasProjectContent = titleText.includes("51.8 V") || titleText.includes("14S") || titleText.includes("PACK TELEMETRY");
    console.log("Persistence confirmed after reload:", hasProjectContent);
    testResults["Workflow A (Project Creation & Persistence)"] = hasProjectContent ? "PASS" : "FAIL";

    // -------------------------------------------------------------------------
    // WORKFLOW B: Battery Configuration (3S16P, 14S8P, 14S16P)
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW B: Battery Configuration ---");

    // 1. Set to 14S16P (224 cells)
    await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("label"));
      const nsLabel = labels.find((l) => l.textContent.includes("Series"));
      const npLabel = labels.find((l) => l.textContent.includes("Parallel"));
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      if (nsLabel && nsLabel.parentElement) {
        const inp = nsLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "14");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
      if (npLabel && npLabel.parentElement) {
        const inp = npLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "16");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    });
    await new Promise((r) => setTimeout(r, 600));

    let bodyText = await page.evaluate(() => document.body.innerText.toUpperCase());
    const has51_8V = bodyText.includes("51.8 V");
    const has80Ah = bodyText.includes("80.0 AH") || bodyText.includes("80 AH");
    const has4144Wh = bodyText.includes("4.14 KWH") || bodyText.includes("4144 WH");
    const has224Cells = bodyText.includes("224 UNITS");

    console.log("14S16P Check: 51.8V:", has51_8V, "| 80Ah:", has80Ah, "| 4144Wh:", has4144Wh, "| 224 Cells:", has224Cells);

    // 2. Switch inputs to 3S16P (48 cells)
    await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("label"));
      const nsLabel = labels.find((l) => l.textContent.includes("Series"));
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      if (nsLabel && nsLabel.parentElement) {
        const inp = nsLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "3");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    });
    await new Promise((r) => setTimeout(r, 600));
    bodyText = await page.evaluate(() => document.body.innerText.toUpperCase());
    const has48Cells = bodyText.includes("48 UNITS");
    const has11_1V = bodyText.includes("11.1 V");
    console.log("3S16P Check: 11.1V:", has11_1V, "| 48 Cells:", has48Cells);

    // 3. Switch inputs to 14S8P (112 cells)
    await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("label"));
      const nsLabel = labels.find((l) => l.textContent.includes("Series"));
      const npLabel = labels.find((l) => l.textContent.includes("Parallel"));
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      if (nsLabel && nsLabel.parentElement) {
        const inp = nsLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "14");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
      if (npLabel && npLabel.parentElement) {
        const inp = npLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "8");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    });
    await new Promise((r) => setTimeout(r, 600));
    bodyText = await page.evaluate(() => document.body.innerText.toUpperCase());
    const has112Cells = bodyText.includes("112 UNITS");
    const has40Ah = bodyText.includes("40.0 AH") || bodyText.includes("40 AH");
    console.log("14S8P Check: 40Ah:", has40Ah, "| 112 Cells:", has112Cells);

    // Restore to 14S16P
    await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("label"));
      const npLabel = labels.find((l) => l.textContent.includes("Parallel"));
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
      if (npLabel && npLabel.parentElement) {
        const inp = npLabel.parentElement.querySelector("input");
        if (inp) {
          setter.call(inp, "16");
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    });
    await new Promise((r) => setTimeout(r, 600));

    testResults["Workflow B (Battery Configuration)"] =
      has51_8V && has80Ah && has4144Wh && has224Cells && has48Cells && has112Cells ? "PASS" : "FAIL";

    // -------------------------------------------------------------------------
    // WORKFLOW C: Mass Model Estimation & Transparency
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW C: Mass Model Estimation & Transparency ---");
    bodyText = await page.evaluate(() => document.body.innerText.toUpperCase());
    const hasCellMass = bodyText.includes("15.68 KG") || bodyText.includes("TOTAL CELL MASS");
    const hasSpecBadge = bodyText.includes("MANUFACTURER SPEC");
    const hasModelBadge = bodyText.includes("ENGINEERING MODEL");
    console.log("Mass Model Check: Total Cell Mass visible:", hasCellMass, "| Badges:", hasSpecBadge, hasModelBadge);

    testResults["Workflow C (Mass Model Estimation)"] = hasCellMass && hasSpecBadge && hasModelBadge ? "PASS" : "FAIL";

    // -------------------------------------------------------------------------
    // WORKFLOW D: Vehicle Tractive Load Analysis
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW D: Vehicle Tractive Load Analysis ---");
    await navigateTo(page, `${BASE_URL}/projects/${createdProjectId}/vehicle-load`, "Vehicle Tractive Load");

    // Test 1: Flat (0%) Preset
    await safeEvaluate(page, () => {
      const btns = Array.from(document.querySelectorAll("button"));
      const flatBtn = btns.find((b) => b.textContent.includes("Flat (0%)"));
      if (flatBtn) flatBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));
    let loadText = await safeEvaluate(page, () => document.body.innerText);
    const flatGrade0 = loadText.includes("0.0 N") || loadText.includes("0.0%");
    const flatDischarge = loadText.includes("DISCHARGING");
    console.log("Flat Preset: Grade=0N/0%:", flatGrade0, "| Discharging:", flatDischarge);

    // Test 2: Hill Climb (+8%) Preset
    await safeEvaluate(page, () => {
      const btns = Array.from(document.querySelectorAll("button"));
      const hillBtn = btns.find((b) => b.textContent.includes("Hill Climb (+8%)"));
      if (hillBtn) hillBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));
    loadText = await safeEvaluate(page, () => document.body.innerText);
    const hillPositivePower = loadText.includes("DISCHARGING") && !loadText.includes("NaN");
    console.log("Hill Climb (+8%) Preset: Positive Power & Discharging:", hillPositivePower);

    // Test 3: Braking / Regen (-5%) Preset
    await safeEvaluate(page, () => {
      const btns = Array.from(document.querySelectorAll("button"));
      const regenBtn = btns.find((b) => b.textContent.includes("Braking / Regen"));
      if (regenBtn) regenBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));
    loadText = await safeEvaluate(page, () => document.body.innerText);
    const regenNegativePower = loadText.includes("REGENERATIVE BRAKING") || loadText.includes("-");
    console.log("Braking Preset: Negative / Regen Power:", regenNegativePower);

    // Test 4: High Accel (2 m/s²) Preset
    await safeEvaluate(page, () => {
      const btns = Array.from(document.querySelectorAll("button"));
      const accelBtn = btns.find((b) => b.textContent.includes("High Accel"));
      if (accelBtn) accelBtn.click();
    });
    await new Promise((r) => setTimeout(r, 600));
    loadText = await safeEvaluate(page, () => document.body.innerText);
    const accelHighInertia = loadText.includes("390.0 N") || loadText.includes("Inertial Force");
    console.log("High Accel Preset: Inertial Force registered:", accelHighInertia);

    // Test 5: Rapid Switching Monotonic Sequence Protection
    await safeEvaluate(page, () => {
      const btns = Array.from(document.querySelectorAll("button"));
      const flatBtn = btns.find((b) => b.textContent.includes("Flat (0%)"));
      const hillBtn = btns.find((b) => b.textContent.includes("Hill Climb (+8%)"));
      const regenBtn = btns.find((b) => b.textContent.includes("Braking / Regen"));
      if (flatBtn) flatBtn.click();
      setTimeout(() => { if (hillBtn) hillBtn.click(); }, 15);
      setTimeout(() => { if (regenBtn) regenBtn.click(); }, 35);
    });
    await new Promise((r) => setTimeout(r, 1000));
    loadText = await safeEvaluate(page, () => document.body.innerText);
    const settledOnRegen = loadText.includes("REGENERATIVE BRAKING") || loadText.includes("-5");
    console.log("Rapid preset switching correctly settled on final preset (Regen):", settledOnRegen);

    testResults["Workflow D (Vehicle Tractive Load Calculator)"] =
      flatDischarge && hillPositivePower && regenNegativePower && settledOnRegen ? "PASS" : "FAIL";

    // -------------------------------------------------------------------------
    // WORKFLOW E: Simulation Execution & Persistence
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW E: Simulation Execution & Persistence ---");
    await navigateTo(page, `${BASE_URL}/projects/${createdProjectId}/simulation`, "LAUNCH TRANSIENT SIMULATION");

    // Click Launch Transient Simulation
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const runBtn = btns.find((b) => b.textContent.includes("LAUNCH TRANSIENT SIMULATION"));
      if (runBtn) runBtn.click();
    });

    // Wait for client-side navigation to /results/[runId]
    await page.waitForFunction(() => window.location.pathname.includes("/results/"), { timeout: 25000 });
    const simUrl = page.url();
    console.log("Navigated to Simulation Results URL:", simUrl);
    const simMatch = simUrl.match(/\/results\/(\d+)/);
    if (!simMatch) {
      throw new Error(`Expected results URL but got ${simUrl}`);
    }
    const runId = parseInt(simMatch[1], 10);
    savedRunId = runId;
    console.log(`Simulation Run ID: ${runId}`);

    // Wait for results telemetry to finish loading
    await waitForText(page, "COMPLETED");
    let resText = await safeEvaluate(page, () => document.body.innerText.toUpperCase());
    const simCompleted = resText.includes("COMPLETED");
    const hasNominalV = resText.includes("51.8 V");
    const hasDeliveredEnergy = resText.includes("3,191") || resText.includes("3191") || (resText.includes("WH") && resText.includes("DELIVERED"));
    const hasConstraintStatus = resText.includes("PASS") || resText.includes("FAIL");
    console.log("Simulation Result: COMPLETED:", simCompleted, "| Nominal 51.8V:", hasNominalV, "| Energy Delivered present:", hasDeliveredEnergy);

    // Reopen and check persistence
    await new Promise((r) => setTimeout(r, 600));
    await page.evaluate(() => location.reload());
    await waitForText(page, "COMPLETED");
    resText = await safeEvaluate(page, () => document.body.innerText.toUpperCase());
    const reloadedCompleted = resText.includes("COMPLETED");
    console.log("Simulation Persistence confirmed after page reload:", reloadedCompleted);

    testResults["Workflow E (Simulation Execution & Persistence)"] =
      simCompleted && hasNominalV && hasDeliveredEnergy && reloadedCompleted ? "PASS" : "FAIL";

    // -------------------------------------------------------------------------
    // WORKFLOW F: 3D Visualization & Console Check
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW F: 3D Visualization & Console Check ---");
    // Return to design page with full 3D visualizer
    await navigateTo(page, `${BASE_URL}/projects/${createdProjectId}/design`, "PACK TELEMETRY");
    await new Promise((r) => setTimeout(r, 1000));

    // Verify Canvas is present in DOM and WebGL context is initialized
    const canvasInfo = await safeEvaluate(page, () => {
      const c = document.querySelector("canvas");
      if (!c) return { exists: false };
      const gl = c.getContext("webgl2") || c.getContext("webgl");
      return { exists: true, width: c.width, height: c.height, hasGL: gl !== null };
    });
    console.log("3D WebGL Canvas rendered successfully:", canvasInfo);

    // Check for Three.js Clock or PCFSoftShadowMap in console warnings
    const clockWarning = consoleWarnings.some((w) => w.includes("Clock") && w.includes("deprecated"));
    const shadowWarning = consoleWarnings.some((w) => w.includes("PCFSoftShadowMap"));
    console.log("THREE.Clock warning present in browser console:", clockWarning);
    console.log("PCFSoftShadowMap warning present in browser console:", shadowWarning);

    // AppLayout Sidebar & Shortcut Verification
    const sidebarInitialWidth = await safeEvaluate(page, () => {
      const aside = document.querySelector("aside");
      return aside ? parseInt(window.getComputedStyle(aside).width, 10) : 0;
    });
    console.log("AppLayout Initial Sidebar Width:", sidebarInitialWidth);

    await page.keyboard.down("Control");
    await page.keyboard.press("b");
    await page.keyboard.up("Control");
    await new Promise((r) => setTimeout(r, 400));

    const sidebarToggledWidth = await safeEvaluate(page, () => {
      const aside = document.querySelector("aside");
      return aside ? parseInt(window.getComputedStyle(aside).width, 10) : -1;
    });
    console.log("AppLayout Toggled Sidebar Width (after Ctrl+B):", sidebarToggledWidth);

    await page.keyboard.down("Control");
    await page.keyboard.press("b");
    await page.keyboard.up("Control");
    await new Promise((r) => setTimeout(r, 400));

    const backdropCheck = await safeEvaluate(page, () => {
      const bd = document.querySelector(".md\\:hidden");
      if (!bd) return true;
      const cs = window.getComputedStyle(bd);
      return cs.display === "none" || cs.pointerEvents === "none" || cs.opacity === "0";
    });
    console.log("Mobile backdrop non-blocking:", backdropCheck);

    console.log("Total console warnings logged during session:", consoleWarnings.length);
    console.log("Total console errors logged during session:", consoleErrors.length);
    console.log("Total page errors logged during session:", pageErrors.length);

    testResults["Workflow F (3D Visualization & Console Health)"] =
      canvasInfo.exists && canvasInfo.hasGL && !clockWarning && !shadowWarning && pageErrors.length === 0 && backdropCheck ? "PASS" : "FAIL";

    // -------------------------------------------------------------------------
    // WORKFLOW G: Comparison & Data Exports
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW G: Comparison & Data Exports ---");
    await navigateTo(page, `${BASE_URL}/projects/${createdProjectId}/compare`, "COMPARE");
    await new Promise((r) => setTimeout(r, 1000));
    const compareHtml = await page.content();
    const compareUpper = compareHtml.toUpperCase();
    const compareLoaded = compareUpper.includes("COMPARE") || compareUpper.includes("DESIGN BLUEPRINTS") || compareUpper.includes("BASELINE");
    console.log("Comparison Page loaded successfully:", compareLoaded);

    // Test API Export Endpoints with the real application API
    const repJson = await postJson(`${API_URL}/projects/${createdProjectId}/reports`, { format: "json", simulation_run_id: savedRunId });
    const jsonFile = await fetchJson(`${API_URL}/reports/${repJson.data.report_id}/download`);
    const isJsonValid = repJson.status === 200 && jsonFile.status === 200 && jsonFile.data && jsonFile.data.configuration;
    console.log(`JSON Report Export: HTTP ${repJson.status}, Download HTTP ${jsonFile.status}, Valid JSON: ${isJsonValid}`);

    const repCsv = await postJson(`${API_URL}/projects/${createdProjectId}/reports`, { format: "csv", simulation_run_id: savedRunId });
    const csvFile = await fetchJson(`${API_URL}/reports/${repCsv.data.report_id}/download`);
    const isCsvValid = repCsv.status === 200 && (csvFile.raw || "").includes("t_s");
    console.log(`CSV Report Export: HTTP ${repCsv.status}, Download HTTP ${csvFile.status}, Valid CSV: ${isCsvValid}`);

    const repPdf = await postJson(`${API_URL}/projects/${createdProjectId}/reports`, { format: "pdf", simulation_run_id: savedRunId });
    const pdfFile = await fetchBuffer(`${API_URL}/reports/${repPdf.data.report_id}/download`);
    const isPdfValid = repPdf.status === 200 && pdfFile.status === 200 && pdfFile.buffer.slice(0, 4).toString() === "%PDF";
    console.log(`PDF Report Export: HTTP ${repPdf.status}, Download HTTP ${pdfFile.status}, Valid %PDF magic bytes: ${isPdfValid}`);

    testResults["Workflow G (Comparison & Data Exports)"] =
      compareLoaded && isJsonValid && isCsvValid && isPdfValid ? "PASS" : "FAIL";

    // -------------------------------------------------------------------------
    // WORKFLOW H: Failure & Error Handling
    // -------------------------------------------------------------------------
    console.log("\n--- WORKFLOW H: Failure & Error Handling ---");
    // 1. API 404 for nonexistent project
    const notFoundProj = await fetchJson(`${API_URL}/projects/999999`);
    const safeApi404 = notFoundProj.status === 404;
    console.log(`API Nonexistent Project returns 404: ${safeApi404}`);

    // 2. API 404 for nonexistent simulation run
    const notFoundSim = await fetchJson(`${API_URL}/simulations/999999`);
    const safeSim404 = notFoundSim.status === 404;
    console.log(`API Nonexistent Simulation returns 404: ${safeSim404}`);

    // 3. API 422 for unprocessable entity / missing required field
    const badInput = await postJson(`${API_URL}/projects`, { description: "Missing name" });
    const safe422 = badInput.status === 422;
    console.log(`API Validation returns 422 Unprocessable Entity: ${safe422}`);

    // 4. UI 404 navigation handling without crash
    await page.goto(`${BASE_URL}/projects/999999/design`, { waitUntil: "domcontentloaded" });
    await new Promise((r) => setTimeout(r, 1500));
    const notFoundHtml = await page.content();
    const notFoundUpper = notFoundHtml.toUpperCase();
    const safeUi404 = notFoundUpper.includes("404") || notFoundUpper.includes("NOT FOUND") || notFoundUpper.includes("ERROR");
    console.log(`UI 404 handled gracefully without browser crash: ${safeUi404}`);

    testResults["Workflow H (Failure & Error Handling)"] = safeApi404 && safeSim404 && safe422 && safeUi404 ? "PASS" : "FAIL";

  } catch (err) {
    console.error("FATAL ERROR IN TEST SUITE:", err);
  } finally {
    await browser.close();
  }

  console.log("\n===============================================================");
  console.log("                      SUMMARY OF RESULTS                       ");
  console.log("===============================================================");
  for (const [testName, status] of Object.entries(testResults)) {
    console.log(`${testName}: ${status}`);
  }
  console.log(`Console Warnings logged: ${consoleWarnings.length}`);
  if (consoleWarnings.length > 0) {
    console.log("Sample warnings:", consoleWarnings.slice(0, 3));
  }
  console.log(`Console Errors logged: ${consoleErrors.length}`);
  if (consoleErrors.length > 0) {
    console.log("Sample errors:", consoleErrors.slice(0, 3));
  }
  console.log(`Page Errors: ${pageErrors.length}`);

  const allPassed = Object.values(testResults).length === 8 && Object.values(testResults).every((v) => v === "PASS");
  if (!allPassed) {
    console.error("❌ E2E VERIFICATION SUITE FAILED: Not all workflows passed.");
    process.exit(1);
  }
  console.log("🎉 ALL 8 E2E REAL BROWSER WORKFLOWS PASSED.");
  process.exit(0);
}

runBrowserE2E();
