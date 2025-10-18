import { useState, useRef, useCallback, useEffect } from 'react';
import { markdownToText } from '../utils/markdownToText';

interface UseSpeechSynthesisReturn {
  speak: (text: string) => void;
  stop: () => void;
  isSpeaking: boolean;
  isSupported: boolean;
}

export const useSpeechSynthesis = (): UseSpeechSynthesisReturn => {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

  useEffect(() => {
    if (!isSupported) return;
    const loadVoices = () => {
      const voices = speechSynthesis.getVoices();
      // console.log('Available voices:', voices.map(v => `${v.name} (${v.lang})`));
    };
    loadVoices();
    speechSynthesis.addEventListener('voiceschanged', loadVoices);
    
    return () => {
      speechSynthesis.removeEventListener('voiceschanged', loadVoices);
    };
  }, [isSupported]);

  // Get Mark voice
  const getMarkVoice = useCallback(() => {
    if (!isSupported) return null;
    
    const voices = speechSynthesis.getVoices();
    const markVoice = voices.find(voice => {
      const name = voice.name.toLowerCase();
      const lang = voice.lang.toLowerCase();
      return (name.includes('mark') || name.includes('Mark')) && 
             (lang.startsWith('en-us') || lang.startsWith('en'));
    });
    
    // Return Mark voice if found, or else go for fallbacks
    return markVoice || voices.find(voice => 
      voice.lang === 'en-US' && voice.localService === true
    ) || voices.find(voice => 
      voice.lang.startsWith('en-US')
    ) || voices.find(voice => 
      voice.lang.startsWith('en') && voice.localService === true
    ) || null;
  }, [isSupported]);

  const stop = useCallback(() => {
    if (isSupported) {
      try {
        speechSynthesis.cancel();
        setTimeout(() => {
          setIsSpeaking(false);
        }, 100);
      } catch (error) {
        console.warn('Error stopping speech:', error);
        setIsSpeaking(false);
      }
    }
  }, [isSupported]);

  const speak = useCallback((text: string) => {
    if (!isSupported) {
      console.warn('Speech synthesis is not supported in this browser');
      return;
    }
    if (speechSynthesis.speaking) {
      speechSynthesis.cancel();
    }

    if (!text.trim()) return;

    const plainText = markdownToText(text);
    
    if (!plainText.trim()) return;

    setTimeout(() => {
      try {
        const utterance = new SpeechSynthesisUtterance(plainText);
        
        const markVoice = getMarkVoice();
        if (markVoice) {
          utterance.voice = markVoice;
          utterance.lang = markVoice.lang;
          // console.log('Using Mark voice:', markVoice.name, markVoice.lang);
        } 
        else {
          utterance.lang = 'en-US';
          // console.log('Mark voice not found, using default voice with en-US language');
        }
        
        // speech settings
        utterance.rate = 0.85;
        utterance.pitch = 1.0;
        utterance.volume = 0.9;

        utterance.onstart = () => {
          // console.log('Speech started');
          setIsSpeaking(true);
        };

        utterance.onend = () => {
          // console.log('Speech ended');
          setIsSpeaking(false);
        };

        utterance.onerror = (event) => {
          console.warn('Speech synthesis error:', event.error, event);
          if (event.error !== 'interrupted') {
            console.error('Unexpected speech error:', event);
          }
          setIsSpeaking(false);
        };

        utterance.onpause = () => {
          // console.log('Speech paused');
          setIsSpeaking(false);
        };

        utterance.onresume = () => {
          // console.log('Speech resumed');
          setIsSpeaking(true);
        };

        utteranceRef.current = utterance;

        speechSynthesis.speak(utterance);
      } catch (error) {
        console.error('Error creating speech:', error);
        setIsSpeaking(false);
      }
    }, 200);
  }, [isSupported, getMarkVoice]);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    speak,
    stop,
    isSpeaking,
    isSupported,
  };
};