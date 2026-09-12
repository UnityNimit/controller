import React from 'react';
import { useGamepad } from './hooks/useGamepad';
import Preset1 from './components/Preset1';
import Preset2 from './components/Preset2';
import SettingsModal from './components/SettingsModal';
import EngageModal from './components/EngageModal';
import './App.css';

export default function App() {
  const gamepad = useGamepad();
  const {
    preset,
    setPreset,
    settingsOpen,
    setSettingsOpen,
    engaged,
    engage,
    gyroEnabled,
    toggleGyro,
    zeroGyro,
    rawAngle,
    playerSlot,
    cyclePreferredSlot,
    connected,
    rtt,
    hapticsEngine
  } = gamepad;

  return (
    <div id="controller-app" className="controller-root">
      {/* Active Layout Preset */}
      {preset === 'preset2' ? (
        <Preset2
          gamepad={gamepad}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      ) : (
        <Preset1
          gamepad={gamepad}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      )}

      {/* Settings & Preset Selector Glassmorphism Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        preset={preset}
        onSelectPreset={setPreset}
        gyroEnabled={gyroEnabled}
        onToggleGyro={toggleGyro}
        onZeroGyro={zeroGyro}
        rawAngle={rawAngle}
        playerSlot={playerSlot}
        onSelectSlot={cyclePreferredSlot}
        connected={connected}
        rtt={rtt}
        hapticsEngine={hapticsEngine}
      />

      {/* Initial Engage & Connect Modal */}
      <EngageModal
        isOpen={!engaged}
        onEngage={engage}
      />
    </div>
  );
}
