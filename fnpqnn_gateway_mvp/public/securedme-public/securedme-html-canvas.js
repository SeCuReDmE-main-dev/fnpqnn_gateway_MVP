/* Read-only capability detection. Existing DOM/canvas rendering remains usable. */
(function () {
  'use strict';
  function detect() {
    const canvas = window.HTMLCanvasElement?.prototype;
    const two = window.CanvasRenderingContext2D?.prototype;
    const gl = window.WebGLRenderingContext?.prototype;
    const gpu = window.GPUQueue?.prototype;
    return Object.freeze({
      htmlInCanvas: typeof two?.drawElementImage === 'function',
      drawableAttribute: !!canvas && 'content' in canvas,
      captureElementImage: typeof canvas?.captureElementImage === 'function',
      updateElementGeometry: typeof canvas?.updateElementGeometry === 'function',
      webgl: typeof gl?.texElementSubImage2D === 'function' ? 'texElementSubImage2D' : typeof gl?.texElementImage2D === 'function' ? 'texElementImage2D' : null,
      webgpu: typeof gpu?.drawElementImageToTexture === 'function' ? 'drawElementImageToTexture' : typeof gpu?.copyElementImageToTexture === 'function' ? 'copyElementImageToTexture' : null
    });
  }
  window.SecuredMeCanvasCapabilities = Object.freeze({detect});
})();
