/**
 * Voice input/output hook — wraps voiceService for React components.
 */

import { useState, useCallback, useEffect } from 'react';
import { voiceService, type VoiceConfig, type VoiceResult } from '../services/voice';

export function useVoice() {
  const [isAvailable, setIsAvailable] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<VoiceConfig>(voiceService.getConfig());

  // ─── Initialize ────────────────────────────────────────────────────────

  useEffect(() => {
    voiceService.init().then((available) => {
      setIsAvailable(available);
    });
  }, []);

  // ─── Speak text ────────────────────────────────────────────────────────

  const speak = useCallback(async (text: string) => {
    if (!isAvailable) return;

    try {
      setIsSpeaking(true);
      setError(null);
      await voiceService.speak(text);
    } catch {
      setError('Failed to speak');
    } finally {
      setIsSpeaking(false);
    }
  }, [isAvailable]);

  // ─── Stop speaking ─────────────────────────────────────────────────────

  const stopSpeaking = useCallback(async () => {
    await voiceService.stopSpeaking();
    setIsSpeaking(false);
  }, []);

  // ─── Process voice message (STT → Nori → TTS) ─────────────────────────

  const processVoice = useCallback(
    async (audioBase64: string, audioFormat = 'wav'): Promise<VoiceResult | null> => {
      setIsProcessing(true);
      setError(null);

      try {
        const result = await voiceService.processVoiceMessage(audioBase64, audioFormat);
        return result;
      } catch {
        setError('Voice processing failed');
        return null;
      } finally {
        setIsProcessing(false);
      }
    },
    [],
  );

  // ─── Toggle recording (placeholder — needs native audio module) ────────

  const toggleRecording = useCallback(() => {
    // In a full implementation, this would use expo-av or a native module
    // to record audio, then call processVoice with the result
    setIsRecording((prev) => !prev);

    if (isRecording) {
      // Stop recording — in production, would capture audio here
      setIsRecording(false);
    } else {
      setIsRecording(true);
      // Start recording — in production, would begin audio capture
    }
  }, [isRecording]);

  // ─── Update config ─────────────────────────────────────────────────────

  const updateConfig = useCallback((updates: Partial<VoiceConfig>) => {
    voiceService.setConfig(updates);
    setConfig(voiceService.getConfig());
  }, []);

  return {
    isAvailable,
    isRecording,
    isSpeaking,
    isProcessing,
    error,
    config,
    speak,
    stopSpeaking,
    processVoice,
    toggleRecording,
    updateConfig,
  };
}
