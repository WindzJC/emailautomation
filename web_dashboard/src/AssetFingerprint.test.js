import { describe, expect, it } from "vitest";

import { contentFingerprint, fingerprintedAssetUrl } from "../../vite.config.js";


describe("frontend asset fingerprints", () => {
  it("changes the legacy app URL when its contents change", () => {
    const first = fingerprintedAssetUrl("/static/app.js", "first app contents");
    const second = fingerprintedAssetUrl("/static/app.js", "second app contents");

    expect(first).toMatch(/^\/static\/app\.js\?v=[a-f0-9]{16}$/);
    expect(second).toMatch(/^\/static\/app\.js\?v=[a-f0-9]{16}$/);
    expect(first).not.toBe(second);
  });

  it("is deterministic for unchanged contents", () => {
    expect(contentFingerprint("unchanged")).toBe(contentFingerprint("unchanged"));
  });
});
