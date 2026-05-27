/** @type {import('next').NextConfig} */
const repoName = process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "";
const isGitHubPages = process.env.GITHUB_PAGES === "true";
const isUserOrOrgSite = repoName.endsWith(".github.io");
const githubPagesBasePath = isGitHubPages && repoName && !isUserOrOrgSite ? `/${repoName}` : "";

const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  ...(githubPagesBasePath
    ? {
        basePath: githubPagesBasePath,
        assetPrefix: `${githubPagesBasePath}/`,
      }
    : {}),
};

export default nextConfig;
