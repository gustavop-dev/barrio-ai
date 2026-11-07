// A stand-in for expo-audio: permissions, a recorder whose state the tests drive, and a player.
import { useState } from 'react';

export const audio = {
  permission: { granted: true, canAskAgain: true, status: 'granted' as string },
  requested: 0,
  recorder: {
    uri: null as string | null,
    currentTime: 0,
    isRecording: false,
    prepareToRecordAsync: jest.fn(async () => undefined),
    record: jest.fn(() => {
      audio.recorder.isRecording = true;
    }),
    pause: jest.fn(() => {
      audio.recorder.isRecording = false;
    }),
    stop: jest.fn(async () => {
      audio.recorder.isRecording = false;
      audio.recorder.uri = 'file:///cache/captura.m4a';
    }),
  },
  player: { play: jest.fn(), pause: jest.fn(), seekTo: jest.fn(async () => undefined) },
};

export function resetFakeAudio() {
  audio.permission = { granted: true, canAskAgain: true, status: 'granted' };
  audio.requested = 0;
  audio.recorder.uri = null;
  audio.recorder.currentTime = 0;
  audio.recorder.isRecording = false;
}

export const expoAudioMock = {
  RecordingPresets: { HIGH_QUALITY: { extension: '.m4a' }, LOW_QUALITY: { extension: '.m4a' } },
  getRecordingPermissionsAsync: jest.fn(async () => ({ ...audio.permission })),
  requestRecordingPermissionsAsync: jest.fn(async () => {
    audio.requested += 1;
    return { ...audio.permission };
  }),
  setAudioModeAsync: jest.fn(async () => undefined),
  useAudioRecorder: () => audio.recorder,
  useAudioRecorderState: () => {
    const [state] = useState({ isRecording: false, durationMillis: 0, canRecord: true, metering: -160 });
    return state;
  },
  useAudioPlayer: () => audio.player,
  useAudioPlayerStatus: () => ({ playing: false, didJustFinish: false, currentTime: 0, duration: 0 }),
};
