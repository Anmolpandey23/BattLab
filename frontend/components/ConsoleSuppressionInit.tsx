"use client";

// Targeted suppression of third-party Three.js / @react-three/drei notices in React 19:
// 1. THREE.Clock deprecation emitted inside @react-three/fiber root store creation
// 2. THREE.WebGLShadowMap: PCFSoftShadowMap removal emitted during legacy shadow setup
// 3. Drei <Html> root unmount timing warning: "Attempted to synchronously unmount a root while React was already rendering"
// Preserves all application warnings, authentic React errors, and diagnostic messages.
if (typeof console !== "undefined") {
  if (typeof console.warn === "function") {
    const originalWarn = console.warn;
    if (!(originalWarn as unknown as { __battlab_wrapped?: boolean }).__battlab_wrapped) {
      const wrappedWarn = (...args: unknown[]) => {
        const msg = typeof args[0] === "string" ? args[0] : "";
        if (
          msg.includes("Clock: This module has been deprecated") ||
          msg.includes("PCFSoftShadowMap has been removed") ||
          msg.includes("Attempted to synchronously unmount a root while React was already rendering") ||
          msg.includes("rendering with server caches disabled") ||
          msg.includes("cache-bypass-in-dev")
        ) {
          return;
        }
        originalWarn.apply(console, args);
      };
      (wrappedWarn as unknown as { __battlab_wrapped: boolean }).__battlab_wrapped = true;
      console.warn = wrappedWarn;
    }
  }

  if (typeof console.error === "function") {
    const originalError = console.error;
    if (!(originalError as unknown as { __battlab_wrapped?: boolean }).__battlab_wrapped) {
      const wrappedError = (...args: unknown[]) => {
        const msg = typeof args[0] === "string" ? args[0] : "";
        if (msg.includes("Attempted to synchronously unmount a root while React was already rendering")) {
          return;
        }
        originalError.apply(console, args);
      };
      (wrappedError as unknown as { __battlab_wrapped: boolean }).__battlab_wrapped = true;
      console.error = wrappedError;
    }
  }
}

export function ConsoleSuppressionInit() {
  return null;
}

export default ConsoleSuppressionInit;

