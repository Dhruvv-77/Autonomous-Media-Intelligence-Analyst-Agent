import React, { useState, useMemo } from 'react';
import { 
  FileText, ShieldCheck, AlertTriangle, Building2, ExternalLink, 
  Copy, Check, Eye, Code, Newspaper, CheckCircle2, ShieldAlert
} from 'lucide-react';

export default function ExecutiveBriefingView({ 
  rawMarkdown, 
  language = 'nl', 
  companyName = 'Global Logistics NV',
  onInspectClaim
}) {
  const [viewMode, setViewMode] = useState('executive'); // 'executive' | 'analyst' | 'raw'
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!rawMarkdown) return;
    navigator.clipboard.writeText(rawMarkdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Structured parser for briefing sections
  const parsedData = useMemo(() => {
    if (!rawMarkdown) return null;

    const parseCitation = (line) => {
      let cleanLine = line.replace(/^-\s*/, '').trim();
      cleanLine = cleanLine.replace(/^(Volgens berichtgeving:\s*|Laut Berichterstattung:\s*)/i, '').trim();

      const citationIdx = cleanLine.indexOf('[[Bron:');
      if (citationIdx === -1) {
        return { text: cleanLine, citation: null };
      }

      const claimText = cleanLine.substring(0, citationIdx).trim();
      const citationPart = cleanLine.substring(citationIdx);

      const idMatch = citationPart.match(/\[\[Bron:\s*([^\]]+)\]\(([^)]+)\)/);
      const spanMatch = citationPart.match(/Span:\s*([0-9-]+)/);
      const evidenceMatch = citationPart.match(/Evidence:\s*(\*?".*?"?\*?)/);

      return {
        text: claimText,
        citation: {
          artId: idMatch ? idMatch[1] : 'Source',
          url: idMatch ? idMatch[2] : '#',
          span: spanMatch ? spanMatch[1] : null,
          evidence: evidenceMatch ? evidenceMatch[1].replace(/^[*\s"]+|[*\s"]+$/g, '') : null
        }
      };
    };

    const lines = rawMarkdown.split('\n');
    let title = language === 'de' ? 'Tägliches Media Intelligence Briefing' : 'Dagelijkse Media Intelligence Briefing';
    let dateStr = '';
    let currentSection = '';
    
    let summaryText = '';
    const topStories = [];
    const risks = [];
    const competitors = [];
    let verificationNote = '';

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;

      if (line.startsWith('# ')) {
        title = line.replace('# ', '').trim();
      } else if (line.startsWith('**Datum') || line.startsWith('**Date')) {
        dateStr = line.replace(/\*\*/g, '').trim();
      } else if (line.startsWith('## 1.') || line.toLowerCase().includes('managementsamenvatting') || line.toLowerCase().includes('management-zusammenfassung')) {
        currentSection = 'summary';
      } else if (line.startsWith('## 2.') || line.toLowerCase().includes('belangrijkste nieuwsfeiten') || line.toLowerCase().includes('hauptmeldungen')) {
        currentSection = 'top_stories';
      } else if (line.startsWith('## 3.') || line.toLowerCase().includes('reputatierisico') || line.toLowerCase().includes('reputationsrisiken')) {
        currentSection = 'risks';
      } else if (line.startsWith('## 4.') || line.toLowerCase().includes('concurrentie') || line.toLowerCase().includes('wettbewerber')) {
        currentSection = 'competitors';
      } else if (line.startsWith('## 5.') || line.toLowerCase().includes('bronverantwoording') || line.toLowerCase().includes('quellen')) {
        currentSection = 'verification';
      } else {
        if (currentSection === 'summary') {
          summaryText += (summaryText ? ' ' : '') + line;
        } else if (currentSection === 'top_stories' && line.startsWith('-')) {
          topStories.push(parseCitation(line));
        } else if (currentSection === 'risks' && line.startsWith('-')) {
          risks.push(parseCitation(line));
        } else if (currentSection === 'competitors' && line.startsWith('-')) {
          competitors.push(parseCitation(line));
        } else if (currentSection === 'verification') {
          verificationNote += (verificationNote ? ' ' : '') + line;
        }
      }
    }

    return {
      title,
      dateStr,
      summaryText,
      topStories,
      risks,
      competitors,
      verificationNote
    };
  }, [rawMarkdown, language]);

  if (!rawMarkdown) {
    return (
      <div style={{ textAlign: 'center', padding: '64px 0', color: 'var(--text-muted)' }}>
        No briefing generated yet. Run the pipeline to produce a verified briefing.
      </div>
    );
  }

  // Format bold markdown text in summary
  const renderFormattedText = (txt) => {
    if (!txt) return null;
    const parts = txt.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} style={{ color: '#fff' }}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Action Toolbar */}
      <div className="briefing-toolbar">
        <div className="view-toggle-group">
          <button 
            className={`view-toggle-btn ${viewMode === 'executive' ? 'active' : ''}`}
            onClick={() => setViewMode('executive')}
          >
            <Newspaper size={14} />
            <span>Executive Reader</span>
          </button>

          <button 
            className={`view-toggle-btn ${viewMode === 'analyst' ? 'active' : ''}`}
            onClick={() => setViewMode('analyst')}
          >
            <Eye size={14} />
            <span>Analyst Audit View</span>
          </button>

          <button 
            className={`view-toggle-btn ${viewMode === 'raw' ? 'active' : ''}`}
            onClick={() => setViewMode('raw')}
          >
            <Code size={14} />
            <span>Raw Markdown</span>
          </button>
        </div>

        <button 
          className="btn btn-secondary" 
          onClick={handleCopy}
          style={{ padding: '6px 14px', fontSize: '0.8rem' }}
        >
          {copied ? <Check size={14} style={{ color: 'var(--accent-emerald)' }} /> : <Copy size={14} />}
          <span>{copied ? 'Copied to Clipboard' : 'Copy Full Briefing'}</span>
        </button>
      </div>

      {/* Raw Markdown View Mode */}
      {viewMode === 'raw' && (
        <div className="exec-document">
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', color: 'var(--text-main)', fontSize: '0.9rem', lineHeight: '1.7' }}>
            {rawMarkdown}
          </pre>
        </div>
      )}

      {/* Executive / Analyst Document View */}
      {viewMode !== 'raw' && parsedData && (
        <div className="exec-document">
          {/* Document Header */}
          <div className="doc-header-card">
            <div className="doc-title-area">
              <h1>
                <FileText className="text-teal" size={26} />
                {parsedData.title}
              </h1>
              <div className="doc-meta-row">
                <span className="doc-meta-item">
                  <Building2 size={14} /> <strong>{companyName}</strong>
                </span>
                <span>•</span>
                <span className="doc-meta-item">{parsedData.dateStr || 'Latest Run'}</span>
                <span>•</span>
                <span className="badge-tag" style={{ padding: '3px 10px', fontSize: '0.75rem' }}>
                  {language === 'de' ? '🇩🇪 Deutsch' : '🇳🇱 Nederlands'}
                </span>
                <span className="badge-tag" style={{ background: 'rgba(16, 185, 129, 0.12)', color: 'var(--accent-emerald)', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                  <ShieldCheck size={12} /> Strictly Citation-Grounded
                </span>
              </div>
            </div>
          </div>

          {/* Section 1: Executive Summary */}
          {parsedData.summaryText && (
            <div className="exec-summary-box">
              <div className="exec-summary-heading">
                <ShieldCheck size={18} />
                <span>{language === 'de' ? '1. Management-Zusammenfassung' : '1. Managementsamenvatting'}</span>
              </div>

              {/* KPI metrics row */}
              <div className="exec-metrics-row">
                <div className="exec-metric-card">
                  <span className="exec-metric-lbl">{language === 'de' ? 'Top-Meldungen' : 'Belangrijke Berichten'}</span>
                  <span className="exec-metric-val" style={{ color: 'var(--accent-teal)' }}>
                    {parsedData.topStories.length}
                  </span>
                </div>

                <div className="exec-metric-card">
                  <span className="exec-metric-lbl">{language === 'de' ? 'Reputationsrisiken' : 'Gedetecteerde Risico\'s'}</span>
                  <span className="exec-metric-val" style={{ color: parsedData.risks.length > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
                    {parsedData.risks.length}
                  </span>
                </div>

                <div className="exec-metric-card">
                  <span className="exec-metric-lbl">{language === 'de' ? 'Wettbewerber-Signale' : 'Concurrentie-Signalen'}</span>
                  <span className="exec-metric-val" style={{ color: '#818cf8' }}>
                    {parsedData.competitors.length}
                  </span>
                </div>
              </div>

              <p style={{ margin: 0, fontSize: '0.98rem', lineHeight: '1.7', color: '#e2e8f0' }}>
                {renderFormattedText(parsedData.summaryText)}
              </p>
            </div>
          )}

          {/* Section 2: Top Stories */}
          {parsedData.topStories.length > 0 && (
            <div className="exec-section-card">
              <div className="exec-section-title">
                <Newspaper size={18} className="text-teal" />
                <span>{language === 'de' ? '2. Hauptmeldungen' : '2. Belangrijkste Nieuwsfeiten'}</span>
              </div>

              <div className="story-cards-list">
                {parsedData.topStories.map((item, idx) => (
                  <div key={idx} className="story-bullet-card">
                    <div className="story-prose">
                      {item.text}
                      {item.citation && (
                        <a 
                          href={item.citation.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="citation-chip"
                          onClick={(e) => {
                            if (onInspectClaim) {
                              e.preventDefault();
                              onInspectClaim(item.citation.artId);
                            }
                          }}
                          title={`Verified Evidence Source:\n${item.citation.evidence || 'Click to view evidence'}`}
                        >
                          <ExternalLink size={10} />
                          <span>{item.citation.artId}</span>
                        </a>
                      )}
                    </div>

                    {/* Detailed Audit metadata for Analyst mode */}
                    {viewMode === 'analyst' && item.citation && (
                      <div className="citation-audit-box">
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--accent-teal)' }}>
                          <span><strong>Evidence Span:</strong> [{item.citation.span}]</span>
                          <span className="mono" style={{ fontSize: '0.75rem' }}>body[{item.citation.span}]</span>
                        </div>
                        {item.citation.evidence && (
                          <div style={{ fontStyle: 'italic', color: '#cbd5e1' }}>
                            "{item.citation.evidence}"
                          </div>
                        )}
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', wordBreak: 'break-all' }}>
                          URL: {item.citation.url}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 3: Reputational Risks & Threats */}
          {parsedData.risks.length > 0 && (
            <div className="exec-section-card">
              <div className="exec-section-title">
                <ShieldAlert size={18} style={{ color: 'var(--accent-rose)' }} />
                <span>{language === 'de' ? '3. Reputationsrisiken & Warnsignale' : '3. Reputatierisico\'s en Dreigingen'}</span>
              </div>

              <div className="story-cards-list">
                {parsedData.risks.map((item, idx) => (
                  <div key={idx} className="story-bullet-card risk">
                    <div className="story-prose">
                      {item.text}
                      {item.citation && (
                        <a 
                          href={item.citation.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="citation-chip"
                          style={{ borderColor: 'rgba(244, 63, 94, 0.4)', color: 'var(--accent-rose)', background: 'rgba(244, 63, 94, 0.1)' }}
                          onClick={(e) => {
                            if (onInspectClaim) {
                              e.preventDefault();
                              onInspectClaim(item.citation.artId);
                            }
                          }}
                          title={`Risk Citation:\n${item.citation.evidence || 'Click to inspect proof'}`}
                        >
                          <AlertTriangle size={10} />
                          <span>{item.citation.artId}</span>
                        </a>
                      )}
                    </div>

                    {viewMode === 'analyst' && item.citation && (
                      <div className="citation-audit-box" style={{ borderColor: 'rgba(244, 63, 94, 0.3)' }}>
                        <div style={{ color: 'var(--accent-rose)' }}>
                          <strong>Risk Evidence Span:</strong> [{item.citation.span}]
                        </div>
                        {item.citation.evidence && (
                          <div style={{ fontStyle: 'italic', color: '#cbd5e1' }}>
                            "{item.citation.evidence}"
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 4: Competitor Activity */}
          {parsedData.competitors.length > 0 && (
            <div className="exec-section-card">
              <div className="exec-section-title">
                <Building2 size={18} style={{ color: '#818cf8' }} />
                <span>{language === 'de' ? '4. Wettbewerber-Aktivitäten' : '4. Concurrentieactiviteit'}</span>
              </div>

              <div className="story-cards-list">
                {parsedData.competitors.map((item, idx) => (
                  <div key={idx} className="story-bullet-card competitor">
                    <div className="story-prose">
                      {item.text}
                      {item.citation && (
                        <a 
                          href={item.citation.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="citation-chip"
                          style={{ borderColor: 'rgba(129, 140, 248, 0.4)', color: '#818cf8', background: 'rgba(129, 140, 248, 0.1)' }}
                          onClick={(e) => {
                            if (onInspectClaim) {
                              e.preventDefault();
                              onInspectClaim(item.citation.artId);
                            }
                          }}
                          title={`Competitor Citation: ${item.citation.artId}`}
                        >
                          <ExternalLink size={10} />
                          <span>{item.citation.artId}</span>
                        </a>
                      )}
                    </div>

                    {viewMode === 'analyst' && item.citation && (
                      <div className="citation-audit-box">
                        <div style={{ color: '#818cf8' }}>
                          <strong>Competitor Evidence Span:</strong> [{item.citation.span}]
                        </div>
                        {item.citation.evidence && (
                          <div style={{ fontStyle: 'italic', color: '#cbd5e1' }}>
                            "{item.citation.evidence}"
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 5: Verification & Governance Seal */}
          <div className="verification-seal-box">
            <CheckCircle2 size={24} style={{ color: 'var(--accent-emerald)', flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 700, color: '#fff', marginBottom: '2px' }}>
                {language === 'de' ? '5. Quellenverifikation & Governance-Prüfung' : '5. Bronverantwoording & Verificatie'}
              </div>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
                {parsedData.verificationNote || 'Alle vermelde feiten zijn cryptografisch en tekstueel gecontroleerd tegen de exacte brontekst. Claims zonder gevalideerde citaties zijn conform auditvereisten afgewezen.'}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
