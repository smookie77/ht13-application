import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces .next/standalone with only the node_modules actually needed.
  // On a Raspberry Pi that is the difference between a ~1.5GB image and a
  // small one, and it keeps the build off the device's limited storage.
  output: "standalone",
};

export default nextConfig;
