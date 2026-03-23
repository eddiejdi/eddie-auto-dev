(function (root) {
  const EXPLICIT_SELECTORS = {
    theme: ['#marketingTheme', 'input[name="theme"]'],
    audience: ['#marketingAudience', 'input[name="audience"]'],
    notes: ['#marketingNotes', '#requestNotes', 'textarea[name="notes"]'],
    name: ['#businessCardName', 'input[name="name"]'],
    title: ['#businessCardTitle', '#requestRole', 'input[name="title"]', 'input[name="cargo"]', 'input[name="role"]'],
    role: ['#requestRole', 'input[name="role"]'],
    email: ['#businessCardEmail', '#requestEmail', '#resellerEmail', 'input[name="email"]', 'input[name="resellerEmail"]'],
    phone: ['#businessCardPhone', '#requestPhone', 'input[type="tel"]', 'input[name="phone"]', 'input[name="telefone"]'],
    tagline: ['#businessCardTagline'],
    specialties: ['#businessCardSpecialties'],
    note: ['#businessCardNote'],
    company: ['#requestCompany', 'input[name="company"]'],
    legal_name: ['#requestLegalName', 'input[name="legalName"]'],
    company_document: ['#requestCompanyDocument', 'input[name="companyDocument"]'],
    contact: ['#requestContact', 'input[name="contact"]'],
    representative_document: ['#requestRepresentativeDocument', 'input[name="representativeDocument"]'],
    project: ['#requestProject', 'input[name="project"]'],
    address: ['#requestAddress', 'input[name="address"]'],
    address_number: ['#requestAddressNumber', 'input[name="addressNumber"]'],
    address_complement: ['#requestAddressComplement', 'input[name="addressComplement"]'],
    district: ['#requestDistrict', 'input[name="district"]'],
    postal_code: ['#requestPostalCode', 'input[name="postalCode"]'],
    temperature: ['#requestTemperature', '#storageTemperature', '#resellerTemperature', 'select[name="temperature"]'],
    volume: ['#requestVolume', '#storageVolume', '#resellerVolume', 'input[name="volume"]'],
    ingress: ['#requestIngress', '#storageIngress', '#resellerIngress', 'input[name="ingress"]'],
    retention: ['#requestRetention', '#storageRetention', '#resellerRetention', 'select[name="retention"]'],
    retrieval: ['#requestRetrieval', '#storageRetrieval', '#resellerRetrieval', 'select[name="retrieval"]'],
    sla: ['#requestSla', '#storageSla', '#resellerSla', 'select[name="sla"]'],
    compliance: ['#requestCompliance', '#storageCompliance', '#resellerCompliance', 'select[name="compliance"]'],
    redundancy: ['#requestRedundancy', '#storageRedundancy', '#resellerRedundancy', 'select[name="redundancy"]'],
    billing: ['#requestBilling', '#resellerBilling', 'select[name="billing"]', 'select[name="billingModel"]'],
    term: ['#requestTerm', '#resellerTerm', 'select[name="term"]', 'select[name="contractTerm"]'],
    start_date: ['#requestStartDate', 'input[name="startDate"]'],
    city: ['#requestCity', 'input[name="city"]'],
    state: ['#requestState', 'input[name="state"]'],
    reseller_company: ['#resellerCompany', 'input[name="resellerCompany"]'],
    reseller_contact: ['#resellerContact', 'input[name="resellerContact"]'],
    reseller_email: ['#resellerEmail', 'input[name="resellerEmail"]'],
    reseller_customer: ['#resellerCustomer', 'input[name="resellerCustomer"]'],
    partner_model: ['#resellerModel', 'select[name="partnerModel"]']
  };

  const KEY_ALIASES = {
    nome: 'name',
    full_name: 'name',
    nome_completo: 'name',
    company_name: 'company',
    company_real_name: 'company',
    real_company_name: 'company',
    business_name: 'company',
    nome_empresa: 'company',
    nome_real_empresa: 'company',
    empresa: 'company',
    empresa_solicitante: 'company',
    cargo: 'title',
    role: 'title',
    telefone: 'phone',
    celular: 'phone',
    observacoes: 'notes',
    observacao: 'notes',
    publico: 'audience',
    publico_alvo: 'audience',
    tema: 'theme',
    razao_social: 'legal_name',
    nome_legal: 'legal_name',
    nome_juridico: 'legal_name',
    cnpj: 'company_document',
    cpf: 'representative_document',
    cpf_representante: 'representative_document',
    telefone_contato: 'phone',
    cargo_area: 'title',
    logradouro: 'address',
    numero: 'address_number',
    complemento: 'address_complement',
    bairro: 'district',
    cep: 'postal_code',
    uf: 'state',
    volume_tb: 'volume',
    novos_dados_mes_tb: 'ingress',
    inicio_pretendido: 'start_date',
    vigencia: 'term',
    recuperacoes: 'retrieval',
    faturamento: 'billing',
    empresa_revendedora: 'reseller_company',
    revenda_empresa: 'reseller_company',
    responsavel_comercial: 'reseller_contact',
    contato_comercial: 'reseller_contact',
    email_comercial: 'reseller_email',
    cliente_final: 'reseller_customer',
    oportunidade: 'reseller_customer',
    modelo_parceiro: 'partner_model',
    regime_faturamento: 'billing',
    vigencia_contratual: 'term'
  };

  const KEY_TOKEN_ALIASES = {
    company: ['empresa'],
    document: ['documento'],
    company_document: ['empresa', 'cnpj', 'documento'],
    representative: ['representante'],
    representative_document: ['representante', 'cpf', 'documento'],
    legal_name: ['razao', 'social'],
    phone: ['telefone', 'celular'],
    state: ['uf'],
    notes: ['observacoes', 'observacao']
  };

  const FIELD_CANDIDATE_SELECTOR = 'input, textarea, select';

  function normalize(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();
  }

  function normalizeKey(key) {
    const compact = normalize(key).replace(/[^a-z0-9]+/g, '_');
    return KEY_ALIASES[compact] || compact;
  }

  function flattenObject(obj, prefix, out) {
    if (!obj || typeof obj !== 'object') {
      return out;
    }

    Object.keys(obj).forEach((key) => {
      const value = obj[key];
      const currentKey = prefix ? `${prefix}.${key}` : key;
      if (value == null) {
        return;
      }
      if (Array.isArray(value)) {
        out[currentKey] = value.join(', ');
        return;
      }
      if (typeof value === 'object') {
        flattenObject(value, currentKey, out);
        return;
      }
      out[currentKey] = value;
    });

    return out;
  }

  function preparePayloadEntries(payload) {
    const flat = flattenObject(payload, '', {});
    const normalizedEntries = Object.entries(flat).map(([key, value]) => ({
      key,
      value,
      normalizedLeaf: normalizeKey(key.split('.').slice(-1)[0])
    }));

    const hasCompany = normalizedEntries.some((entry) => entry.normalizedLeaf === 'company' && String(entry.value || '').trim());
    const companyFallback = normalizedEntries.find((entry) => (
      entry.normalizedLeaf === 'legal_name' ||
      entry.normalizedLeaf === 'company_name'
    ) && String(entry.value || '').trim());

    if (!hasCompany && companyFallback) {
      flat.company = companyFallback.value;
    }

    return flat;
  }

  function getFieldContextText(field) {
    const fragments = [];
    const pushText = (value) => {
      const text = normalize(value);
      if (text && !fragments.includes(text)) {
        fragments.push(text);
      }
    };

    if (field.labels && field.labels.length) {
      Array.from(field.labels).forEach((label) => pushText(label.innerText || label.textContent));
    }

    const labelByFor = field.id ? document.querySelector(`label[for="${CSS.escape(field.id)}"]`) : null;
    if (labelByFor) {
      pushText(labelByFor.innerText || labelByFor.textContent);
    }

    const wrapper = field.closest('label, .form-group, .form-field, .field, .input-group, .ant-form-item, .MuiFormControl-root, td, th, li, section, article, div');
    if (wrapper) {
      pushText(wrapper.innerText || wrapper.textContent);
    }

    pushText(field.previousElementSibling && (field.previousElementSibling.innerText || field.previousElementSibling.textContent));
    pushText(field.parentElement && (field.parentElement.innerText || field.parentElement.textContent));

    return fragments;
  }

  function getFieldDescriptor(field) {
    const attrs = [
      field.id,
      field.name,
      field.type,
      field.getAttribute('placeholder'),
      field.getAttribute('aria-label'),
      field.getAttribute('data-testid'),
      field.getAttribute('autocomplete'),
      field.getAttribute('title'),
      ...getFieldContextText(field)
    ]
      .filter(Boolean)
      .map((item) => normalize(item));

    return {
      node: field,
      attrs,
      fingerprint: attrs.join(' ')
    };
  }

  function usableField(field) {
    if (!field || field.disabled) {
      return false;
    }
    const type = normalize(field.type);
    if (type === 'hidden' || type === 'submit' || type === 'button' || type === 'reset' || type === 'file') {
      return false;
    }
    return true;
  }

  function isFieldVisible(field) {
    if (!usableField(field)) {
      return false;
    }
    const rect = typeof field.getBoundingClientRect === 'function' ? field.getBoundingClientRect() : null;
    const style = window.getComputedStyle(field);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
      return false;
    }
    if (!rect) {
      return true;
    }
    return rect.width > 0 && rect.height > 0;
  }

  function isFieldEmpty(field) {
    const type = normalize(field.type);
    if (type === 'checkbox' || type === 'radio') {
      return !field.checked;
    }
    return normalize(field.value) === '';
  }

  function scoreField(descriptor, normalizedKey) {
    const key = normalize(normalizedKey);
    if (!key) {
      return 0;
    }

    const keyTokens = Array.from(new Set(
      key
        .split('_')
        .filter(Boolean)
        .concat(KEY_TOKEN_ALIASES[key] || [])
    ));

    let score = 0;
    descriptor.attrs.forEach((attr) => {
      if (attr === key) {
        score += 100;
      }
      if (attr.includes(key)) {
        score += 50;
      }
      const tokenHits = keyTokens.filter((token) => attr.includes(token));
      score += tokenHits.length * 10;
    });
    return score;
  }

  function setFieldValue(field, rawValue) {
    const type = normalize(field.type);
    const value = rawValue == null ? '' : rawValue;

    if (field.tagName === 'SELECT') {
      const target = normalize(value);
      const options = Array.from(field.options || []);
      const exact = options.find((opt) => normalize(opt.value) === target || normalize(opt.textContent) === target);
      if (exact) {
        field.value = exact.value;
        return true;
      }

      const partial = options.find((opt) => {
        const optValue = normalize(opt.value);
        const optText = normalize(opt.textContent);
        return target.includes(optValue) || target.includes(optText) || optValue.includes(target) || optText.includes(target);
      });
      if (partial) {
        field.value = partial.value;
        return true;
      }

      const numberInTarget = target.match(/\d+/);
      if (numberInTarget) {
        const byNumber = options.find((opt) => {
          const candidate = normalize(opt.value + ' ' + opt.textContent).match(/\d+/);
          return candidate && candidate[0] === numberInTarget[0];
        });
        if (byNumber) {
          field.value = byNumber.value;
          return true;
        }
      }

      field.value = String(value);
      return true;
    }

    if (type === 'checkbox') {
      field.checked = typeof value === 'boolean' ? value : ['1', 'true', 'yes', 'sim', 'on'].includes(normalize(value));
      return true;
    }

    if (type === 'radio') {
      const group = document.querySelectorAll(`input[type="radio"][name="${CSS.escape(field.name || '')}"]`);
      const pick = Array.from(group).find((node) => normalize(node.value) === normalize(value));
      if (pick) {
        pick.checked = true;
        return true;
      }
      return false;
    }

    field.value = String(value);
    return true;
  }

  function emitEvents(field) {
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function valueLooksCompatible(field, rawValue, keyHint) {
    const value = String(rawValue == null ? '' : rawValue).trim();
    const type = normalize(field.type);
    const digits = value.replace(/\D/g, '');
    const fingerprint = normalize(
      [
        field.name,
        field.id,
        field.getAttribute('placeholder'),
        field.getAttribute('aria-label'),
        keyHint
      ]
        .filter(Boolean)
        .join(' ')
    );

    if (!value) {
      return false;
    }

    if (field.tagName === 'SELECT') {
      return true;
    }

    if (fingerprint.includes('cnpj') || (fingerprint.includes('empresa') && fingerprint.includes('document'))) {
      return digits.length === 14;
    }

    if (fingerprint.includes('cpf') || fingerprint.includes('representante')) {
      return digits.length === 11;
    }

    if (type === 'email' || fingerprint.includes('email') || fingerprint.includes('e-mail')) {
      return value.includes('@');
    }

    if (type === 'tel' || fingerprint.includes('phone') || fingerprint.includes('telefone') || fingerprint.includes('celular')) {
      return /\d{8,}/.test(value.replace(/\D/g, ''));
    }

    if (type === 'date' || fingerprint.includes('data')) {
      return /\d{4}-\d{2}-\d{2}/.test(value) || /\d{2}\/\d{2}\/\d{4}/.test(value);
    }

    if (type === 'number') {
      return /^-?\d+([.,]\d+)?$/.test(value);
    }

    return true;
  }

  function fillWithExplicitSelectors(key, value, usedNodes) {
    const selectors = EXPLICIT_SELECTORS[key];
    if (!selectors) {
      return null;
    }

    for (const selector of selectors) {
      const field = document.querySelector(selector);
      if (!usableField(field) || usedNodes.has(field)) {
        continue;
      }
      if (setFieldValue(field, value)) {
        emitEvents(field);
        usedNodes.add(field);
        return field;
      }
    }

    return null;
  }

  function fillResidualFields(entries, descriptors, usedNodes) {
    let filled = 0;

    entries.forEach(([key, value]) => {
      if (value == null || value === '') {
        return;
      }

      let best = null;
      let bestScore = -1;
      descriptors.forEach((descriptor) => {
        const field = descriptor.node;
        if (usedNodes.has(field) || !isFieldVisible(field) || !isFieldEmpty(field)) {
          return;
        }
        if (!valueLooksCompatible(field, value, key)) {
          return;
        }

        const relaxedScore = scoreField(descriptor, normalizeKey(key.split('.').slice(-1)[0]));
        if (relaxedScore > bestScore) {
          best = descriptor;
          bestScore = relaxedScore;
        }
      });

      if (best && setFieldValue(best.node, value)) {
        emitEvents(best.node);
        usedNodes.add(best.node);
        filled += 1;
      }
    });

    return filled;
  }

  function fillForm(payload) {
    const flat = preparePayloadEntries(payload);
    const descriptors = Array.from(document.querySelectorAll(FIELD_CANDIDATE_SELECTOR))
      .filter(usableField)
      .map(getFieldDescriptor);

    const usedNodes = new Set();
    const matchedKeys = new Set();
    let filled = 0;
    const keys = Object.keys(flat);

    keys.forEach((sourceKey) => {
      const value = flat[sourceKey];
      const leafKey = sourceKey.split('.').slice(-1)[0];
      const normalizedKey = normalizeKey(leafKey);

      const explicitField = fillWithExplicitSelectors(normalizedKey, value, usedNodes);
      if (explicitField) {
        matchedKeys.add(sourceKey);
        filled += 1;
        return;
      }

      let best = null;
      let bestScore = 0;
      descriptors.forEach((descriptor) => {
        if (usedNodes.has(descriptor.node)) {
          return;
        }
        if (!valueLooksCompatible(descriptor.node, value, normalizedKey)) {
          return;
        }
        const currentScore = scoreField(descriptor, normalizedKey);
        if (currentScore > bestScore) {
          bestScore = currentScore;
          best = descriptor;
        }
      });

      if (best && bestScore >= 20 && setFieldValue(best.node, value)) {
        emitEvents(best.node);
        usedNodes.add(best.node);
        matchedKeys.add(sourceKey);
        filled += 1;
      }
    });

    const unmatchedEntries = keys
      .filter((key) => !matchedKeys.has(key))
      .map((key) => [key, flat[key]]);

    filled += fillResidualFields(unmatchedEntries, descriptors, usedNodes);

    return {
      filled,
      totalKeys: keys.length,
      page: window.location && window.location.href ? window.location.href : ''
    };
  }

  root.RPA4AllAutofillCore = {
    EXPLICIT_SELECTORS,
    KEY_ALIASES,
    FIELD_CANDIDATE_SELECTOR,
    normalize,
    normalizeKey,
    flattenObject,
    fillForm
  };
})(typeof globalThis !== 'undefined' ? globalThis : window);
