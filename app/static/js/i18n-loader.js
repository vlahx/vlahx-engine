/**
 * i18n-loader.js - Manager de traduceri pentru blog
 */

// Dicționar de traduceri (poate veni din JSON sau API)
const translations = {
    'ro': {
        common: {
            langSelector: '🌐',
            welcomeMessage: 'Bine ai venit pe blogul meu!',
            description: 'Aici găsești articole interesante despre dezvoltare web, design și tehnologie.',
            postsTitle: 'Articole Recente',
            author: 'Autor',
            date: 'Data',
            readMore: 'Citește mai mult'
        },
        meta: {
            title: 'Blogul Meu - Home'
        }
    },
    'en': {
        common: {
            langSelector: '🌐',
            welcomeMessage: 'Welcome to my blog!',
            description: 'Here you will find interesting articles about web development, design and technology.',
            postsTitle: 'Recent Articles',
            author: 'Author',
            date: 'Date',
            readMore: 'Read More'
        },
        meta: {
            title: 'My Blog - Home'
        }
    }
};

/**
 * Schimbă limba curentă
 * @param {string} lang - Codul limbii (ro/en)
 */
function changeLanguage(lang) {
    // Salvează preferința în localStorage
    localStorage.setItem('blog_lang', lang);
    
    // Obține dicționarul pentru limba selectată
    const t = translations[lang];
    
    if (!t) return;
    
    // 1. Actualizează titlul paginii și meta
    const title = document.querySelector('title');
    if (title) {
        title.textContent = t.meta.title;
    }
    
    // 2. Înlocuiește textele prin selectori de clasă sau atribut data-i18n
    const elementsToTranslate = [
        // Elementele cu clasă specifică
        { selector: '.navbar-brand', key: 'title' },
        { selector: '.hero-section h1', key: 'common.welcomeMessage' },
        { selector: '.hero-section p', key: 'common.description' },
        { selector: '.content-wrapper h2', key: 'common.postsTitle' },
        
        // Selectează toate elementele cu data-i18n
        { selector: '[data-i18n]', key: function(el) { 
            return `common.${el.getAttribute('data-i18n')}`; 
        }}
    ];
    
    elementsToTranslate.forEach(item => {
        const el = document.querySelector(item.selector);
        if (el && item.key.includes('.')) {
            // Key cu punct - e o structură obiect
            const keys = item.key.split('.');
            let text = t;
            for (const k of keys) {
                text = text && text[k];
            }
            el.textContent = text || '';
        } else if (item.key instanceof Function) {
            // Key este o funcție - apelăm-o cu elementul curent
            const key = item.key(el);
            const text = t && t[Object.keys(t).find(k => k.includes(key))];
            el.textContent = text || '';
        } else if (item.key instanceof String) {
            const text = t[item.key] || '';
            el.textContent = text;
        }
    });
    
    // 3. Înlocuiește atributurile dinamic (data, year, etc.)
    document.querySelectorAll('[data-i18n-date]').forEach(el => {
        const dateKey = el.getAttribute('data-i18n-date');
        let date = new Date();
        if (dateKey === 'year') {
            date = date.getFullYear();
        } else if (dateKey === 'currentDate') {
            date = date.toLocaleDateString(lang);
        }
        el.textContent = date;
    });
    
    // 4. Actualizează limba în header
    const langSelector = document.getElementById('langDropdown');
    if (langSelector) {
        const currentText = langSelector.firstChild?.textContent || '';
        const newBtnText = translations[lang]?.common.langSelector + ' ' + 
            (lang === 'ro' ? 'Română' : 'English');
        langSelector.firstChild.textContent = newBtnText;
    }
    
    console.log(`Switched to language: ${lang}`);
}

// Inițializare - setează limba implicită
document.addEventListener('DOMContentLoaded', () => {
    const savedLang = localStorage.getItem('blog_lang') || 'ro';
    changeLanguage(savedLang);
    
    // Ascultăm click-uri pe selectorul de limbă (Bootstrap)
    const langDropdown = document.getElementById('langDropdown');
    if (langDropdown) {
        langDropdown.addEventListener('shown.bs.dropdown', function() {
            // Limba curentă din localStorage se va afișa deja în dropdown
        });
    }
});

/**
 * Extensie pentru Bootstrap - asigurăm că limbile sunt corecte
 */
document.addEventListener('DOMContentLoaded', () => {
    // Setează atributul lang pe HTML pentru SEO și accesibilitate
    const savedLang = localStorage.getItem('blog_lang') || 'ro';
    document.documentElement.lang = savedLang;
    
    // Dacă există un selector de limbă în dropdown, actualizează textul butonului
    const langToggle = document.querySelector('[data-bs-toggle="dropdown"]');
    if (langToggle) {
        const langButton = langToggle.firstChild;
        langButton.textContent = translations[savedLang]?.common.langSelector + ' ' + 
            (savedLang === 'ro' ? 'Română' : 'English');
    }
});

// Export funcții pentru utilizare în alte fișiere
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { changeLanguage, translations };
}