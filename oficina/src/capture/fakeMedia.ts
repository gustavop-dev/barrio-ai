// Test double for the browser's microphone (getUserMedia) and MediaRecorder, which jsdom lacks.
// Only tests import it.
import { vi } from 'vitest';

export class FakeMediaRecorder extends EventTarget {
  static isTypeSupported = (type: string) => type.startsWith('audio/webm');
  static instances: FakeMediaRecorder[] = [];
  state: 'inactive' | 'recording' | 'paused' = 'inactive';
  mimeType: string;

  constructor(_stream: unknown, options?: { mimeType?: string }) {
    super();
    this.mimeType = options?.mimeType ?? 'audio/webm';
    FakeMediaRecorder.instances.push(this);
  }

  start() {
    this.state = 'recording';
  }

  pause() {
    this.state = 'paused';
  }

  resume() {
    this.state = 'recording';
  }

  stop() {
    this.state = 'inactive';
    const event = new Event('dataavailable');
    Object.defineProperty(event, 'data', { value: new Blob(['fake-audio'], { type: this.mimeType }) });
    this.dispatchEvent(event);
    this.dispatchEvent(new Event('stop'));
  }
}

/** Installs a microphone that grants (or denies) access, and the fake recorder. */
export function installFakeMedia({ deny = false }: { deny?: boolean } = {}) {
  FakeMediaRecorder.instances = [];
  const track = { stop: vi.fn() };
  const stream = { getTracks: () => [track] };
  const getUserMedia = vi.fn(async () => {
    if (deny) throw new DOMException('Permission denied', 'NotAllowedError');
    return stream;
  });
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } });
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder);
  return { getUserMedia, track };
}

export function removeFakeMedia() {
  Reflect.deleteProperty(navigator, 'mediaDevices');
}
