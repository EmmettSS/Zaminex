import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveBlob } from "./utils";

type FakeAnchor = {
  href: string;
  download: string;
  appended: boolean;
  clicked: boolean;
  removed: boolean;
  click(): void;
  remove(): void;
};

function installDom(anchors: FakeAnchor[], revoked: string[]) {
  vi.stubGlobal("document", {
    createElement: () => {
      const a: FakeAnchor = {
        href: "",
        download: "",
        appended: false,
        clicked: false,
        removed: false,
        click() {
          this.clicked = true;
        },
        remove() {
          this.removed = true;
        },
      };
      anchors.push(a);
      return a;
    },
    body: { appendChild: (node: FakeAnchor) => void (node.appended = true) },
  });
  
  vi.stubGlobal("window", { setTimeout: (fn: () => void) => setTimeout(fn, 0) });
  vi.stubGlobal("URL", {
    createObjectURL: () => "blob:test",
    revokeObjectURL: (u: string) => void revoked.push(u),
  });
}

let anchors: FakeAnchor[];
let revoked: string[];

beforeEach(() => {
  vi.useFakeTimers();
  anchors = [];
  revoked = [];
  installDom(anchors, revoked);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("saveBlob", () => {
  it("attaches the anchor, sets the filename and clicks it", () => {
    saveBlob(new Blob(["x"]), "report.pdf");

    expect(anchors).toHaveLength(1);
    const a = anchors[0];
    expect(a.appended).toBe(true);
    expect(a.clicked).toBe(true);
    expect(a.download).toBe("report.pdf");
    expect(a.href).toBe("blob:test");
  });

  it("does NOT revoke the object URL synchronously (the 0-byte bug)", () => {
    saveBlob(new Blob(["x"]), "report.pdf");

    expect(revoked).toHaveLength(0);
    expect(anchors[0].removed).toBe(false);
  });

  it("releases the URL and anchor only after the download is handed off", () => {
    saveBlob(new Blob(["x"]), "report.pdf");
    vi.runAllTimers();

    expect(revoked).toEqual(["blob:test"]);
    expect(anchors[0].removed).toBe(true);
  });
});
