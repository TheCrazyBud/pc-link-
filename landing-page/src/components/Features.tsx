import { Mic, Terminal, Code2, Cpu } from 'lucide-react';
import './Features.css';

export default function Features() {
  const features = [
    {
      icon: <Mic size={32} color="#c084fc" />,
      title: 'Groq-Powered Voice',
      description: 'Dictate complex coding tasks directly to your IDE. Whisper AI translates your speech to text with near-instant latency.'
    },
    {
      icon: <Code2 size={32} color="#0A84FF" />,
      title: 'Native IDE Integration',
      description: 'The VS Code Extension injects your prompts directly into the AI assistant seamlessly. No copy-pasting required.'
    },
    {
      icon: <Terminal size={32} color="#34C759" />,
      title: 'Remote Terminals',
      description: 'Spawn, monitor, and control terminals on your PC from anywhere using your mobile app.'
    },
    {
      icon: <Cpu size={32} color="#FF9500" />,
      title: 'Live Telemetry',
      description: 'View live logs, real-time status updates, and agent activity directly on your phone.'
    }
  ];

  return (
    <section className="features-section container" id="docs">
      <div className="features-header">
        <h2>Unleash Your <span className="title-gradient">Workflow</span></h2>
        <p>Everything you need to step away from the keyboard.</p>
      </div>
      
      <div className="features-grid">
        {features.map((feat, idx) => (
          <div key={idx} className="glass-card feature-card">
            <div className="feature-icon">{feat.icon}</div>
            <h3>{feat.title}</h3>
            <p>{feat.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
