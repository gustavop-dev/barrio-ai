// Metro resolves images to an asset id for <Image source>.
declare module '*.png' {
  const source: number;
  export default source;
}
