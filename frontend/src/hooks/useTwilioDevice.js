import { useRef, useState, useCallback, useEffect } from 'react';
import { Device } from '@twilio/voice-sdk';

export function useTwilioDevice() {
  const deviceRef = useRef(null);
  const callRef = useRef(null);
  // Bumped on every initDevice() call - React StrictMode deliberately
  // double-invokes mount effects in dev, and since initDevice is async, a
  // superseded call must recognize it lost the race and tear itself down
  // instead of racing the newer one for deviceRef.current.
  const initGenerationRef = useRef(0);
  const [deviceReady, setDeviceReady] = useState(false);
  const [callState, setCallState] = useState('idle');

  const initDevice = useCallback(async () => {
    const myGeneration = ++initGenerationRef.current;
    try {
      const res = await fetch('/calls/token');
      const { token } = await res.json();

      if (myGeneration !== initGenerationRef.current) {
        console.log('[Twilio Device] Superseded before token resolved - abandoning init');
        return;
      }

      if (deviceRef.current) {
        deviceRef.current.destroy();
      }

      const device = new Device(token, {
        logLevel: 1,
        codecPreferences: ['opus', 'pcmu'],
        // Ensure audio output is enabled
        enableImplicitConstraints: true,
      });

      // Set up audio output to default speakers
      device.audio?.on('deviceChange', () => {
        console.log('[Twilio Device] Audio device changed');
      });

      device.on('registered', () => {
        if (myGeneration !== initGenerationRef.current) return;
        console.log('[Twilio Device] Ready');
        setDeviceReady(true);
      });

      device.on('error', (err) => {
        console.error('[Twilio Device] Error:', err);
      });

      device.on('tokenWillExpire', async () => {
        console.log('[Twilio Device] Token expiring, refreshing...');
        try {
          const res = await fetch('/calls/token');
          const { token: newToken } = await res.json();
          device.updateToken(newToken);
        } catch (e) {
          console.error('[Twilio Device] Token refresh failed:', e);
        }
      });

      device.register();

      if (myGeneration !== initGenerationRef.current) {
        // Superseded while registering - discard this one instead of
        // leaving it as an orphaned, still-registered Device.
        console.log('[Twilio Device] Superseded after register() - destroying');
        device.destroy();
        return;
      }
      deviceRef.current = device;
    } catch (err) {
      console.error('[Twilio Device] Init failed:', err);
    }
  }, []);

  const makeCall = useCallback(async (params) => {
    if (!deviceRef.current) {
      console.error('[Twilio Device] Not initialized');
      return null;
    }

    setCallState('connecting');

    try {
      // Request mic permission explicitly before connecting
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log('[Twilio Call] Mic access granted, tracks:', stream.getAudioTracks().map(t => t.label));
        // Stop the test stream - Twilio SDK will create its own
        stream.getTracks().forEach(t => t.stop());
      } catch (micErr) {
        console.error('[Twilio Call] Mic access DENIED:', micErr);
        setCallState('idle');
        alert('Microphone access is required to make calls. Please allow mic access and try again.');
        return null;
      }

      const call = await deviceRef.current.connect({
        params,
        rtcConstraints: {
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        },
      });

      callRef.current = call;

      call.on('ringing', (hasEarlyMedia) => {
        console.log('[Twilio Call] Ringing, early media:', hasEarlyMedia);
        setCallState('ringing');
      });

      call.on('accept', () => {
        console.log('[Twilio Call] Connected');
        console.log('[Twilio Call] isMuted:', call.isMuted());
        setCallState('connected');

        // Ensure mic is NOT muted
        if (call.isMuted()) {
          call.mute(false);
          console.log('[Twilio Call] Unmuted mic');
        }

        // Check remote audio (what we hear)
        const remoteStream = call.getRemoteStream();
        if (remoteStream) {
          console.log('[Twilio Call] Remote stream active:', remoteStream.active);
          console.log('[Twilio Call] Remote audio tracks:', remoteStream.getAudioTracks().length);
        }

        // Check local audio (our mic)
        const localStream = call.getLocalStream();
        if (localStream) {
          const audioTracks = localStream.getAudioTracks();
          console.log('[Twilio Call] Local stream active:', localStream.active);
          console.log('[Twilio Call] Local audio tracks:', audioTracks.length);
          audioTracks.forEach((track, i) => {
            console.log(`[Twilio Call] Mic track ${i}: enabled=${track.enabled}, muted=${track.muted}, readyState=${track.readyState}, label=${track.label}`);
          });
        } else {
          console.error('[Twilio Call] NO local audio stream - mic not captured!');
        }
      });

      call.on('disconnect', () => {
        console.log('[Twilio Call] Disconnected');
        setCallState('disconnected');
        callRef.current = null;
      });

      call.on('cancel', () => {
        console.log('[Twilio Call] Cancelled');
        setCallState('idle');
        callRef.current = null;
      });

      call.on('error', (err) => {
        console.error('[Twilio Call] Error:', err);
        setCallState('idle');
        callRef.current = null;
      });

      return call;
    } catch (err) {
      console.error('[Twilio Call] Connect failed:', err);
      setCallState('idle');
      return null;
    }
  }, []);

  const hangUp = useCallback(() => {
    if (callRef.current) {
      callRef.current.disconnect();
      callRef.current = null;
    }
    setCallState('idle');
  }, []);

  useEffect(() => {
    return () => {
      if (deviceRef.current) {
        deviceRef.current.destroy();
        deviceRef.current = null;
      }
    };
  }, []);

  const toggleMute = useCallback(() => {
    if (callRef.current) {
      const newMuted = !callRef.current.isMuted();
      callRef.current.mute(newMuted);
      console.log('[Twilio Call] Mute:', newMuted);
      return newMuted;
    }
    return false;
  }, []);

  return {
    initDevice,
    makeCall,
    hangUp,
    toggleMute,
    deviceReady,
    callState,
  };
}
