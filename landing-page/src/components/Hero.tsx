import { ArrowRight, Terminal, Shield, Mic, Activity, Code2 } from 'lucide-react';
import './Hero.css';

export default function Hero() {
  return (
    <section className="hero-section container">
      <div className="hero-content">
        <div className="hero-badge">
          <span className="pulse-dot"></span>
          Now with VS Code Integration
        </div>
        
        <h1 className="hero-title">
          Telepathy for your <span className="title-gradient">IDE</span>
        </h1>
        
        <p className="hero-subtitle">
          Control your code editor with your voice. Connect your phone to your PC instantly. 
          Send prompts, spawn remote terminals, and view live telemetry securely.
        </p>
        
        <div className="hero-actions">
          <a href="#download" className="glass-button primary">
            Download PC Link <ArrowRight size={20} />
          </a>
          <a href="#docs" className="glass-button">
            View Documentation
          </a>
        </div>
        
        <div className="hero-features-preview">
          <div className="feature-pill"><Mic size={16} /> Voice Dictation</div>
          <div className="feature-pill"><Terminal size={16} /> Remote Terminals</div>
          <div className="feature-pill"><Code2 size={16} /> IDE Extension</div>
          <div className="feature-pill"><Shield size={16} /> Hardware Secured</div>
        </div>
      </div>
      
      <div className="hero-visual">
        <div className="visual-glow"></div>
        <img src="/hero.png" alt="PC Link Interface" className="hero-image" />
      </div>
    </section>
  );
}
