import { test, expect } from "@playwright/test";
test("real API: builder, cached preset, report tabs, history, compare and responsive layout", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Was it skill. Or a lucky universe?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /The overfit|overfit/i }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/home-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Audit your strategy", exact: true })
    .click();
  await expect(page.getByText("16 strategy variants")).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Nifty 50 closing prices" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/builder-desktop.png",
    fullPage: true,
  });
  await page.getByLabel("Fast window").fill("5, 5");
  await expect(page.getByText(/unique whole numbers/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Continue", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Fast window").fill("5, 10, 20, 30");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Choose your multiverse" }),
  ).toBeVisible();
  await page.goto("/");
  await page.getByRole("button", { name: /overfit/i }).click();
  await expect(page).toHaveURL(/\/audit\/.*\/run/);
  await expect(page).toHaveURL(/\/audit\/[^/]+$/, { timeout: 30000 });
  await expect(page.locator(".verdict-banner .verdict-chip")).toHaveText(
    "luck",
  );
  await expect(page.locator(".chart-card canvas").first()).toBeVisible();
  await page.screenshot({
    path: "test-results/report-desktop.png",
    fullPage: true,
  });
  for (const name of [
    "Overfitting",
    "Survival",
    "Realism",
    "Trades",
    "Multiverse",
  ]) {
    await page.getByRole("tab", { name, exact: true }).click();
    await expect(
      page.locator("#evidence-panel .chart-card").first(),
    ).toBeVisible();
    await expect(page.getByText("Loading evidence…")).toHaveCount(0);
    await expect(page.locator('#evidence-panel [role="alert"]')).toHaveCount(0);
  }
  await page.goto("/history");
  await expect(page.locator("tbody tr")).not.toHaveCount(0);
  const presets = await (
    await request.get("http://127.0.0.1:8000/api/v1/presets")
  ).json();
  const a = presets[0].cached_audit_id,
    b = presets[1].cached_audit_id;
  await page.goto(`/audit/${b}`);
  for(const name of ['Multiverse','Overfitting','Survival','Realism','Trades']){await page.getByRole('tab',{name,exact:true}).click();await expect(page.locator('#evidence-panel .chart-card').first()).toBeVisible();await expect(page.getByText('Loading evidence…')).toHaveCount(0);await expect(page.locator('#evidence-panel [role="alert"]')).toHaveCount(0);}
  await page.goto(`/compare?a=${a}&b=${b}`);
  await expect(page.locator(".compare-grid .verdict-banner")).toHaveCount(2);
  await expect(page.locator(".compare-grid canvas").first()).toBeVisible();
  for(const name of ['Overfitting','Survival','Realism','Trades','Multiverse']){await page.getByRole('tab',{name,exact:true}).click();await expect(page.getByText('Loading evidence…')).toHaveCount(0);await expect(page.locator('.compare-grid [role="alert"]')).toHaveCount(0);}
  await page.goto('/methods.html#pbo');await expect(page.getByRole('heading',{name:'PBO',exact:true})).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/audit/new");
  await expect(
    page.getByRole("heading", { name: "Put your edge to the test." }),
  ).toBeVisible();
  await expect(page.locator('.market-panel canvas').first()).toBeVisible();
  await expect(page.getByText('Loading market history…')).toHaveCount(0);
  await page.screenshot({
    path: "test-results/builder-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
