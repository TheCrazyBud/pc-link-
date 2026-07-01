import { ShieldCheck, Lock, Fingerprint } from 'lucide-react';
import './SecurityBadge.css';

export default function SecurityBadge() {
  return (
    <section className="security-section container">
      <div className="security-visual">
        <div className="security-glow"></div>
        <img src="/security.png" alt="Hardware Security Chip" className="security-image" />
      </div>
      
      <div className="security-content">
        <div className="security-tag">
          <ShieldCheck size={18} /> Enterprise Grade
        </div>
        <h2>Hardware-Secured <span className="title-gradient">Auth</span></h2>
        <p>
          We take your data seriously. The PC Link daemon binds strictly to your machine's hardware UUID. 
          Combined with Firebase Client Authentication, you're the only one who can access your device.
        </p>
        
        <div className="security-points">
          <div className="sec-point">
            <Lock size={20} color="#34C759" />
            <div>
              <h4>Private Firebase Scoping</h4>
              <span>All prompts and logs are locked to your personal UID.</span>
            </div>
          </div>
          <div className="sec-point">
            <Fingerprint size={20} color="#0A84FF" />
            <div>
              <h4>Motherboard Fingerprinting</h4>
              <span>Daemon locks itself to your hardware automatically.</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
