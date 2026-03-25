export function domainMatches(hostname: string, rules: string[]) {
  return rules.some((rule) => hostname === rule || hostname.endsWith(`.${rule}`));
}

export function normalizeDomainList(raw: string) {
  return raw
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
}
