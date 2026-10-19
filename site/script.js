// Cuttle Landing Page Interactive Logic (P6-05)

document.addEventListener('DOMContentLoaded', () => {
  // 1. Clipboard Copy Functionality
  const copyButtons = document.querySelectorAll('.copy-btn');
  copyButtons.forEach((btn) => {
    btn.addEventListener('click', async () => {
      let textToCopy = btn.getAttribute('data-clipboard');
      if (!textToCopy && btn.id === 'pkg-copy-btn') {
        const codeEl = document.getElementById('pkg-command-text');
        textToCopy = codeEl ? codeEl.textContent : '';
      }

      if (textToCopy) {
        try {
          await navigator.clipboard.writeText(textToCopy);
          const originalHTML = btn.innerHTML;
          btn.innerHTML = '✓';
          btn.style.color = '#10b981';
          setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.style.color = '';
          }, 2000);
        } catch (err) {
          console.error('Failed to copy: ', err);
        }
      }
    });
  });

  // 2. Format Explorer Filtering Tabs
  const formatTabs = document.querySelectorAll('#format-tabs .tab-btn');
  const formatCards = document.querySelectorAll('#format-grid .format-card');

  formatTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      formatTabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');

      const filter = tab.getAttribute('data-filter');
      formatCards.forEach((card) => {
        const category = card.getAttribute('data-cat');
        if (filter === 'all' || category === filter) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });

  // 3. Package Manager Tabs
  const pkgTabs = document.querySelectorAll('.pkg-tab');
  const pkgCommandText = document.getElementById('pkg-command-text');

  const pkgCommands = {
    winget: 'winget install Ameya79.Cuttle',
    scoop: 'scoop bucket add cuttle https://github.com/Ameya79/cuttle && scoop install cuttle',
    choco: 'choco install cuttle',
  };

  pkgTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      pkgTabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');

      const pkg = tab.getAttribute('data-pkg');
      if (pkgCommandText && pkgCommands[pkg]) {
        pkgCommandText.textContent = pkgCommands[pkg];
      }
    });
  });

  // 4. Interactive Context Menu Submenu Item Click Simulation
  const submenuItems = document.querySelectorAll('.mock-submenu .submenu-item');
  submenuItems.forEach((item) => {
    item.addEventListener('click', () => {
      const targetExt = item.getAttribute('data-target');
      showMockToast(`Converting financial_report_2026.pdf ➔ financial_report_2026.${targetExt.toLowerCase()}... Done!`);
    });
  });

  function showMockToast(message) {
    let toast = document.getElementById('mock-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'mock-toast';
      toast.style.position = 'fixed';
      toast.style.bottom = '24px';
      toast.style.right = '24px';
      toast.style.backgroundColor = 'rgba(24, 26, 40, 0.95)';
      toast.style.color = '#f8fafc';
      toast.style.border = '1px solid rgba(99, 102, 241, 0.5)';
      toast.style.borderRadius = '10px';
      toast.style.padding = '14px 20px';
      toast.style.boxShadow = '0 12px 30px rgba(0,0,0,0.6)';
      toast.style.fontSize = '0.9rem';
      toast.style.zIndex = '9999';
      toast.style.display = 'flex';
      toast.style.alignItems = 'center';
      toast.style.gap = '10px';
      toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      document.body.appendChild(toast);
    }

    toast.innerHTML = `<span>🦑</span><span>${message}</span>`;
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
    }, 3000);
  }
});
