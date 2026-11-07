import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { installFakeMedia, removeFakeMedia } from './fakeMedia';
import { audioFilename, getMicState, mmss, Recorder, requestMic, resetMicStateForTests, toBars } from './recorder';

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('recorder helpers', () => {
  it('formats the time and names the file by type', () => {
    expect(mmss(0)).toBe('0:00');
    expect(mmss(42.7)).toBe('0:42');
    expect(mmss(725)).toBe('12:05');
    expect(audioFilename('audio/webm;codecs=opus')).toBe('captura.webm');
    expect(audioFilename('audio/mp4')).toBe('captura.m4a');
    expect(audioFilename('audio/ogg;codecs=opus')).toBe('captura.ogg');
    expect(audioFilename('')).toBe('captura.webm');
  });

  it('downsamples or pads the levels to the bars of the wave', () => {
    expect(toBars([], 4)).toEqual([0, 0, 0, 0]);
    expect(toBars([0.5], 3)).toEqual([0, 0, 0.5]);
    expect(toBars([0.1, 0.9, 0.2, 0.4], 2)).toEqual([0.9, 0.4]);
  });
});

describe('Recorder', () => {
  beforeEach(() => resetMicStateForTests());
  afterEach(() => removeFakeMedia());

  it('records, pauses, resumes and returns the audio when stopped', async () => {
    const { track } = installFakeMedia();
    const recorder = Recorder.start();
    expect(recorder.state).toBe('starting');
    await settle();
    expect(recorder.state).toBe('recording');
    expect(getMicState()).toBe('granted');
    recorder.pause();
    expect(recorder.state).toBe('paused');
    recorder.resume();
    expect(recorder.state).toBe('recording');
    const audio = await recorder.stop();
    expect(recorder.state).toBe('stopped');
    expect(audio?.mime).toBe('audio/webm;codecs=opus');
    expect(audio?.blob.size).toBeGreaterThan(0);
    expect(audio?.levels).toHaveLength(24);
    expect(track.stop).toHaveBeenCalled();
    // Stopping twice gives the same audio.
    expect(await recorder.stop()).toBe(audio);
  });

  it('stops the microphone when discarded, and still returns the audio for «Recuperar»', async () => {
    const { track } = installFakeMedia();
    const recorder = Recorder.start();
    await settle();
    const audio = await recorder.discard();
    expect(audio).not.toBeNull();
    expect(track.stop).toHaveBeenCalled();
  });

  it('fails as denied when the browser refuses the microphone', async () => {
    installFakeMedia({ deny: true });
    const recorder = Recorder.start();
    await settle();
    expect(recorder.state).toBe('error');
    expect(recorder.problem?.problem).toBe('denied');
    expect(getMicState()).toBe('denied');
    expect(await recorder.stop()).toBeNull();
  });

  it('says it cannot record without MediaRecorder', () => {
    const recorder = Recorder.start();
    expect(recorder.state).toBe('error');
    expect(recorder.problem?.problem).toBe('unsupported');
  });

  it('asks for the microphone and lets it go at once', async () => {
    const { getUserMedia, track } = installFakeMedia();
    await expect(requestMic()).resolves.toBe('granted');
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(track.stop).toHaveBeenCalled();
  });
});
