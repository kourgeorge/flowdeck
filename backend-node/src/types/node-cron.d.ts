declare module "node-cron" {
  function schedule(
    expression: string,
    callback: () => void,
    options?: { scheduled?: boolean; timezone?: string }
  ): { start: () => void; stop: () => void; destroy: () => void };
}
