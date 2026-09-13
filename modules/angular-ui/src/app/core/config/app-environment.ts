/** Browser-visible configuration. Internal service URLs and API keys never belong here. */
export const appEnvironment = {
  production: false,
  apiBaseUrl: '/api',
  gatewayOrigin: window.location.origin,
} as const;

export function gatewayUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${appEnvironment.apiBaseUrl}${normalizedPath}`;
}

export function isGatewayUrl(url: string): boolean {
  return url.startsWith(appEnvironment.apiBaseUrl) || url.startsWith(`${appEnvironment.gatewayOrigin}${appEnvironment.apiBaseUrl}`);
}
