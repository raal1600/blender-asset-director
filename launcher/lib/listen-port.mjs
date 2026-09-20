/** Zero requests an OS-assigned loopback port for an isolated staging studio. */
export function listenPort(config) {
  const port=config.port??48731;
  if(!Number.isInteger(port)||port<0||port>65535)throw new Error('Launcher port must be an integer from 0 to 65535.');
  return port;
}
