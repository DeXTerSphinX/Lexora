/**
 * Lexora PDF Export — shared by Upload.html and Admin_Portal.html
 */

function _splitPassage(text) {
    return text
        .split(/(?<=\S)\s+(?=[1-9]\d*\s+[A-Z])/)
        .map(p => p.trim().replace(/^\d+\s+/, ''))
        .filter(p => p.length > 10);
}

function _boldKeywords(text, keywords) {
    if (!keywords || !keywords.length) return text;
    keywords.forEach(word => {
        const esc = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const re  = new RegExp('\\b(' + esc + ')\\b', 'gi');
        text = text.replace(re, '<strong style="color:#b85030;">$1</strong>');
    });
    return text;
}

function buildAndDownloadPDF(result, fileName) {
    const groups = {};
    (result.units || []).forEach(unit => {
        const match = unit.id.match(/^(Q\d+)/);
        if (!match) return;
        const key = match[1];
        if (!groups[key]) groups[key] = { key, header: null, passage: null, instruction: null, subquestions: [] };
        if      (unit.type === 'header')      groups[key].header      = unit;
        else if (unit.type === 'passage')     groups[key].passage     = unit;
        else if (unit.type === 'instruction') groups[key].instruction = unit;
        else if (unit.type === 'subquestion') groups[key].subquestions.push(unit);
    });

    const groupList = Object.values(groups);
    let body = '';

    groupList.forEach((g, i) => {
        const num        = g.key.replace('Q', '');
        const headerText = g.header ? (g.header.modified || g.header.original || '') : '';
        const marks      = g.header && g.header.marks;
        const headerKws  = g.header && g.header.keywords;

        body += `<div style="margin-bottom:36px;page-break-inside:avoid;">`;

        // Question header row
        body += `
            <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;">
                <span style="background:#f0a080;color:#fff;border-radius:8px;padding:5px 13px;font-size:13px;font-weight:bold;white-space:nowrap;margin-top:2px;">Q${num}</span>
                <div style="flex:1;font-size:15px;font-weight:700;line-height:2;letter-spacing:.04em;word-spacing:.12em;">${_boldKeywords(headerText, headerKws)}</div>
                ${marks ? `<span style="background:#fce8dc;border:1px solid #f0a080;border-radius:12px;padding:4px 12px;font-size:12px;color:#b85030;white-space:nowrap;">${marks} marks</span>` : ''}
            </div>`;

        // Passage — split into numbered paragraphs
        if (g.passage && g.passage.modified) {
            const paras = _splitPassage(g.passage.modified);
            const parasHtml = paras.map((p, idx) => `
                <div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
                    <span style="background:#84b8a4;color:#fff;border-radius:50%;width:20px;height:20px;font-size:10px;font-weight:bold;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:4px;">${idx + 1}</span>
                    <p style="margin:0;font-size:14px;line-height:2.1;letter-spacing:.04em;word-spacing:.14em;flex:1;">${_boldKeywords(p, g.passage.keywords)}</p>
                </div>`).join('');
            body += `
                <div style="background:#f0f6f3;border-left:4px solid #84b8a4;padding:16px 20px;margin-bottom:14px;border-radius:0 8px 8px 0;color:#1a3028;">
                    <div style="font-size:10px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:#84b8a4;margin-bottom:10px;">Read this passage first</div>
                    ${parasHtml}
                </div>`;
        }

        // Instruction
        if (g.instruction && g.instruction.modified) {
            body += `<div style="font-size:13px;color:#6b4e3c;margin-bottom:10px;font-style:italic;line-height:1.9;">${g.instruction.modified}</div>`;
        }

        // Subquestions
        g.subquestions.forEach(sq => {
            const text  = sq.modified || sq.original || '';
            const label = (sq.id.match(/(\([^)]+\))/) || [])[1] || '';
            const mPill = sq.marks ? `<span style="color:#a88878;font-size:11px;"> [${sq.marks} marks]</span>` : '';
            body += `
                <div style="display:flex;gap:12px;margin-bottom:10px;font-size:14px;line-height:2;letter-spacing:.03em;word-spacing:.1em;">
                    <span style="font-weight:bold;white-space:nowrap;color:#b85030;min-width:32px;">${label}</span>
                    <div>${_boldKeywords(text, sq.keywords)}${mPill}</div>
                </div>`;
        });

        body += `</div>`;
        if (i < groupList.length - 1) {
            body += `<div style="border-bottom:1px solid #ead8cc;margin-bottom:36px;"></div>`;
        }
    });

    // Load OpenDyslexic web font for the PDF render
    if (!document.getElementById('opendyslexic-font')) {
        const style = document.createElement('style');
        style.id = 'opendyslexic-font';
        style.textContent = `@import url('https://fonts.cdnfonts.com/css/open-dyslexic');`;
        document.head.appendChild(style);
    }

    const container = document.createElement('div');
    container.innerHTML = `
        <div style="font-family:'Open-Dyslexic',OpenDyslexic,Arial,sans-serif;padding:44px;color:#2e2218;">
            <div style="border-bottom:3px solid #f0a080;padding-bottom:14px;margin-bottom:36px;">
                <div style="font-size:22px;font-weight:bold;margin-bottom:4px;">Lexora — Simplified Exam</div>
                <div style="font-size:10px;color:#a88878;letter-spacing:1px;text-transform:uppercase;">${fileName} · Dyslexia-friendly version</div>
            </div>
            ${body}
            <div style="margin-top:48px;padding-top:14px;border-top:1px solid #ead8cc;font-size:10px;color:#a88878;text-align:center;">
                Generated by Lexora · Cognitive-load transformation for dyslexia accessibility
            </div>
        </div>`;

    html2pdf().set({
        margin:      [8, 8, 8, 8],
        filename:    `lexora-${fileName}.pdf`,
        image:       { type: 'jpeg', quality: 0.97 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF:       { unit: 'mm', format: 'a4', orientation: 'portrait' }
    }).from(container).save();
}
