const fs = require('fs');
const path = require('path');
const vm = require('vm');

class FakeEvent {
  constructor(type, init) {
    this.type = type;
    this.bubbles = Boolean(init && init.bubbles);
  }
}

class FakeOption {
  constructor(value, textContent) {
    this.value = value;
    this.textContent = textContent;
  }
}

class FakeTextNode {
  constructor(text) {
    this.innerText = text;
    this.textContent = text;
  }
}

class FakeLabel {
  constructor(text, htmlFor) {
    this.innerText = text;
    this.textContent = text;
    this.htmlFor = htmlFor || '';
  }
}

class FakeWrapper {
  constructor(text) {
    this.innerText = text;
    this.textContent = text;
  }
}

class FakeField {
  constructor(config) {
    this.tagName = config.tagName;
    this.id = config.id || '';
    this.name = config.name || '';
    this.type = config.type || '';
    this.value = config.value || '';
    this.checked = Boolean(config.checked);
    this.disabled = Boolean(config.disabled);
    this.options = config.options || [];
    this.labels = config.labels || [];
    this.previousElementSibling = config.previousElementSibling || null;
    this.parentElement = config.parentElement || null;
    this.wrapper = config.wrapper || null;
    this.attributes = { ...(config.attributes || {}) };
    this.events = [];
  }

  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
  }

  dispatchEvent(event) {
    this.events.push(event.type);
    return true;
  }

  getBoundingClientRect() {
    return { width: 200, height: 40 };
  }

  closest() {
    return this.wrapper;
  }
}

class FakeDocument {
  constructor(fields, labelsByFor, selectorMap) {
    this.fields = fields;
    this.labelsByFor = labelsByFor;
    this.selectorMap = selectorMap;
  }

  querySelectorAll(selector) {
    if (selector === 'input, textarea, select') {
      return this.fields;
    }
    if (selector.startsWith('input[type="radio"][name="')) {
      const name = selector.slice('input[type="radio"][name="'.length, -2);
      return this.fields.filter((field) => field.tagName === 'INPUT' && field.type === 'radio' && field.name === name);
    }
    return [];
  }

  querySelector(selector) {
    if (selector.startsWith('label[for="')) {
      const fieldId = selector.slice('label[for="'.length, -2);
      return this.labelsByFor.get(fieldId) || null;
    }
    return this.selectorMap.get(selector) || null;
  }
}

function createField(config, selectorMap, fields, labelsByFor) {
  const label = config.label ? new FakeLabel(config.label, config.id) : null;
  const wrapper = new FakeWrapper(config.wrapperText || config.label || config.name || config.id || '');
  const previousElementSibling = config.previousText ? new FakeTextNode(config.previousText) : null;
  const parentElement = new FakeWrapper(config.parentText || config.wrapperText || config.label || '');
  const field = new FakeField({
    tagName: config.tagName,
    id: config.id,
    name: config.name,
    type: config.type,
    options: config.options,
    labels: label ? [label] : [],
    previousElementSibling,
    parentElement,
    wrapper,
    attributes: config.attributes
  });

  if (label && config.id) {
    labelsByFor.set(config.id, label);
  }
  (config.selectors || []).forEach((selector) => selectorMap.set(selector, field));
  fields.push(field);
  return field;
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: esperado "${expected}", obtido "${actual}"`);
  }
}

function assertTruthy(value, label) {
  if (!value) {
    throw new Error(`${label}: valor falso`);
  }
}

function loadCoreWithDocument(document) {
  const corePath = path.join(__dirname, 'autofill-core.js');
  const source = fs.readFileSync(corePath, 'utf8');
  const context = {
    console,
    document,
    window: null,
    globalThis: null,
    Event: FakeEvent,
    CSS: { escape: (value) => String(value || '') }
  };
  context.window = context;
  context.globalThis = context;
  context.location = { href: 'https://qa.local/rpa4all-selftest' };
  context.getComputedStyle = () => ({ display: 'block', visibility: 'visible', opacity: '1' });
  vm.runInNewContext(source, context, { filename: corePath });
  return context.RPA4AllAutofillCore;
}

function buildFixture() {
  const fields = [];
  const selectorMap = new Map();
  const labelsByFor = new Map();

  const refs = {
    theme: createField({
      tagName: 'INPUT',
      id: 'marketingTheme',
      name: 'theme',
      type: 'text',
      label: 'Tema da campanha',
      selectors: ['#marketingTheme', 'input[name="theme"]']
    }, selectorMap, fields, labelsByFor),
    audience: createField({
      tagName: 'INPUT',
      name: 'audience',
      type: 'text',
      label: 'Publico alvo',
      attributes: { 'aria-label': 'Publico alvo da campanha' },
      selectors: ['input[name="audience"]']
    }, selectorMap, fields, labelsByFor),
    notes: createField({
      tagName: 'TEXTAREA',
      id: 'requestNotes',
      name: 'notes',
      label: 'Observacoes adicionais',
      attributes: { placeholder: 'Campo propositalmente sem mapeamento exato' },
      selectors: ['#requestNotes', 'textarea[name="notes"]']
    }, selectorMap, fields, labelsByFor),
    company: createField({
      tagName: 'INPUT',
      id: 'requestCompany',
      name: 'company',
      type: 'text',
      label: 'Empresa',
      selectors: ['#requestCompany', 'input[name="company"]']
    }, selectorMap, fields, labelsByFor),
    legalName: createField({
      tagName: 'INPUT',
      id: 'requestLegalName',
      name: 'legalName',
      type: 'text',
      label: 'Razao social',
      selectors: ['#requestLegalName', 'input[name="legalName"]']
    }, selectorMap, fields, labelsByFor),
    contact: createField({
      tagName: 'INPUT',
      id: 'requestContact',
      name: 'contact',
      type: 'text',
      label: 'Contato principal',
      selectors: ['#requestContact', 'input[name="contact"]']
    }, selectorMap, fields, labelsByFor),
    role: createField({
      tagName: 'INPUT',
      id: 'requestRole',
      name: 'role',
      type: 'text',
      label: 'Cargo da area',
      selectors: ['#requestRole', 'input[name="role"]']
    }, selectorMap, fields, labelsByFor),
    email: createField({
      tagName: 'INPUT',
      id: 'requestEmail',
      name: 'email',
      type: 'email',
      label: 'E-mail corporativo',
      selectors: ['#requestEmail', 'input[name="email"]']
    }, selectorMap, fields, labelsByFor),
    phone: createField({
      tagName: 'INPUT',
      id: 'requestPhone',
      name: 'phone',
      type: 'tel',
      label: 'Telefone do responsavel',
      selectors: ['#requestPhone', 'input[name="phone"]', 'input[type="tel"]']
    }, selectorMap, fields, labelsByFor),
    representativeDocument: createField({
      tagName: 'INPUT',
      id: 'requestRepresentativeDocument',
      name: 'representativeDocument',
      type: 'text',
      label: 'CPF do representante',
      selectors: ['#requestRepresentativeDocument', 'input[name="representativeDocument"]']
    }, selectorMap, fields, labelsByFor),
    project: createField({
      tagName: 'INPUT',
      id: 'requestProject',
      name: 'project',
      type: 'text',
      label: 'Projeto',
      selectors: ['#requestProject', 'input[name="project"]']
    }, selectorMap, fields, labelsByFor),
    address: createField({
      tagName: 'INPUT',
      id: 'requestAddress',
      name: 'address',
      type: 'text',
      label: 'Logradouro',
      selectors: ['#requestAddress', 'input[name="address"]']
    }, selectorMap, fields, labelsByFor),
    addressNumber: createField({
      tagName: 'INPUT',
      id: 'requestAddressNumber',
      name: 'addressNumber',
      type: 'text',
      label: 'Numero',
      selectors: ['#requestAddressNumber', 'input[name="addressNumber"]']
    }, selectorMap, fields, labelsByFor),
    addressComplement: createField({
      tagName: 'INPUT',
      id: 'requestAddressComplement',
      name: 'addressComplement',
      type: 'text',
      label: 'Complemento',
      selectors: ['#requestAddressComplement', 'input[name="addressComplement"]']
    }, selectorMap, fields, labelsByFor),
    district: createField({
      tagName: 'INPUT',
      id: 'requestDistrict',
      name: 'district',
      type: 'text',
      label: 'Bairro',
      selectors: ['#requestDistrict', 'input[name="district"]']
    }, selectorMap, fields, labelsByFor),
    postalCode: createField({
      tagName: 'INPUT',
      id: 'requestPostalCode',
      name: 'postalCode',
      type: 'text',
      label: 'CEP',
      selectors: ['#requestPostalCode', 'input[name="postalCode"]']
    }, selectorMap, fields, labelsByFor),
    temperature: createField({
      tagName: 'SELECT',
      id: 'requestTemperature',
      name: 'temperature',
      label: 'Temperatura',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('cold', 'Cold'),
        new FakeOption('warm', 'Warm'),
        new FakeOption('hot', 'Hot')
      ],
      selectors: ['#requestTemperature', 'select[name="temperature"]']
    }, selectorMap, fields, labelsByFor),
    volume: createField({
      tagName: 'INPUT',
      id: 'requestVolume',
      name: 'volume',
      type: 'number',
      label: 'Volume inicial',
      selectors: ['#requestVolume', 'input[name="volume"]']
    }, selectorMap, fields, labelsByFor),
    ingress: createField({
      tagName: 'INPUT',
      id: 'requestIngress',
      name: 'ingress',
      type: 'number',
      label: 'Novos dados por mes',
      selectors: ['#requestIngress', 'input[name="ingress"]']
    }, selectorMap, fields, labelsByFor),
    retention: createField({
      tagName: 'SELECT',
      id: 'requestRetention',
      name: 'retention',
      label: 'Retencao',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('12', '12'),
        new FakeOption('24', '24'),
        new FakeOption('36', '36')
      ],
      selectors: ['#requestRetention', 'select[name="retention"]']
    }, selectorMap, fields, labelsByFor),
    retrieval: createField({
      tagName: 'SELECT',
      id: 'requestRetrieval',
      name: 'retrieval',
      label: 'Recuperacao',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('daily', 'daily'),
        new FakeOption('weekly', 'weekly'),
        new FakeOption('monthly', 'monthly')
      ],
      selectors: ['#requestRetrieval', 'select[name="retrieval"]']
    }, selectorMap, fields, labelsByFor),
    sla: createField({
      tagName: 'SELECT',
      id: 'requestSla',
      name: 'sla',
      label: 'SLA',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('4h', '4h'),
        new FakeOption('24h', '24h'),
        new FakeOption('48h', '48h')
      ],
      selectors: ['#requestSla', 'select[name="sla"]']
    }, selectorMap, fields, labelsByFor),
    compliance: createField({
      tagName: 'SELECT',
      id: 'requestCompliance',
      name: 'compliance',
      label: 'Compliance',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('immutable30', 'immutable30'),
        new FakeOption('lgpd', 'lgpd')
      ],
      selectors: ['#requestCompliance', 'select[name="compliance"]']
    }, selectorMap, fields, labelsByFor),
    redundancy: createField({
      tagName: 'SELECT',
      id: 'requestRedundancy',
      name: 'redundancy',
      label: 'Redundancia',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('single', 'single'),
        new FakeOption('dual', 'dual')
      ],
      selectors: ['#requestRedundancy', 'select[name="redundancy"]']
    }, selectorMap, fields, labelsByFor),
    billing: createField({
      tagName: 'SELECT',
      id: 'requestBilling',
      name: 'billingModel',
      label: 'Modelo de faturamento',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('monthly', 'monthly'),
        new FakeOption('annual', 'annual')
      ],
      selectors: ['#requestBilling', 'select[name="billingModel"]']
    }, selectorMap, fields, labelsByFor),
    term: createField({
      tagName: 'SELECT',
      id: 'requestTerm',
      name: 'contractTerm',
      label: 'Vigencia contratual',
      options: [
        new FakeOption('', 'Selecione'),
        new FakeOption('12', '12'),
        new FakeOption('24', '24'),
        new FakeOption('36', '36')
      ],
      selectors: ['#requestTerm', 'select[name="contractTerm"]']
    }, selectorMap, fields, labelsByFor),
    startDate: createField({
      tagName: 'INPUT',
      id: 'requestStartDate',
      name: 'startDate',
      type: 'date',
      label: 'Inicio pretendido',
      selectors: ['#requestStartDate', 'input[name="startDate"]']
    }, selectorMap, fields, labelsByFor),
    city: createField({
      tagName: 'INPUT',
      id: 'requestCity',
      name: 'city',
      type: 'text',
      label: 'Cidade',
      selectors: ['#requestCity', 'input[name="city"]']
    }, selectorMap, fields, labelsByFor),
    state: createField({
      tagName: 'INPUT',
      id: 'requestState',
      name: 'state',
      type: 'text',
      label: 'UF',
      selectors: ['#requestState', 'input[name="state"]']
    }, selectorMap, fields, labelsByFor),
    heuristicCompanyDocument: createField({
      tagName: 'INPUT',
      id: 'customDoc',
      name: 'documentoEmpresa',
      type: 'text',
      label: 'Documento da empresa',
      attributes: { placeholder: 'CNPJ da empresa' },
      selectors: []
    }, selectorMap, fields, labelsByFor)
  };

  return {
    document: new FakeDocument(fields, labelsByFor, selectorMap),
    refs
  };
}

function run() {
  const samplePath = path.join(__dirname, 'sample-masses.json');
  const sample = JSON.parse(fs.readFileSync(samplePath, 'utf8'));
  const payload = sample.records.find((record) => record.id === 'storage-001').data;

  const fixture = buildFixture();
  const core = loadCoreWithDocument(fixture.document);
  const result = core.fillForm(payload);

  assertEqual(result.filled, result.totalKeys, 'cobertura de preenchimento');
  assertEqual(fixture.refs.company.value, payload.company, 'company');
  assertEqual(fixture.refs.legalName.value, payload.legal_name, 'legal_name');
  assertEqual(fixture.refs.heuristicCompanyDocument.value, payload.company_document, 'heuristic company_document');
  assertEqual(fixture.refs.contact.value, payload.contact, 'contact');
  assertEqual(fixture.refs.role.value, payload.title, 'title -> role');
  assertEqual(fixture.refs.email.value, payload.email, 'email');
  assertEqual(fixture.refs.phone.value, payload.phone, 'phone');
  assertEqual(fixture.refs.representativeDocument.value, payload.representative_document, 'representative_document');
  assertEqual(fixture.refs.project.value, payload.project, 'project');
  assertEqual(fixture.refs.address.value, payload.address, 'address');
  assertEqual(fixture.refs.addressNumber.value, payload.address_number, 'address_number');
  assertEqual(fixture.refs.addressComplement.value, payload.address_complement, 'address_complement');
  assertEqual(fixture.refs.district.value, payload.district, 'district');
  assertEqual(fixture.refs.postalCode.value, payload.postal_code, 'postal_code');
  assertEqual(fixture.refs.temperature.value, payload.temperature, 'temperature');
  assertEqual(fixture.refs.volume.value, payload.volume, 'volume');
  assertEqual(fixture.refs.ingress.value, payload.ingress, 'ingress');
  assertEqual(fixture.refs.retention.value, payload.retention, 'retention');
  assertEqual(fixture.refs.retrieval.value, payload.retrieval, 'retrieval');
  assertEqual(fixture.refs.sla.value, payload.sla, 'sla');
  assertEqual(fixture.refs.compliance.value, payload.compliance, 'compliance');
  assertEqual(fixture.refs.redundancy.value, payload.redundancy, 'redundancy');
  assertEqual(fixture.refs.billing.value, payload.billing, 'billing');
  assertEqual(fixture.refs.term.value, payload.term, 'term');
  assertEqual(fixture.refs.startDate.value, payload.start_date, 'start_date');
  assertEqual(fixture.refs.city.value, payload.city, 'city');
  assertEqual(fixture.refs.state.value, payload.state, 'state');
  assertEqual(fixture.refs.notes.value, payload.notes, 'notes');
  assertTruthy(fixture.refs.company.events.includes('input'), 'company input event');
  assertTruthy(fixture.refs.company.events.includes('change'), 'company change event');

  const fallbackFixture = buildFixture();
  const fallbackCore = loadCoreWithDocument(fallbackFixture.document);
  fallbackCore.fillForm({
    legal_name: payload.legal_name,
    company_document: payload.company_document,
    contact: payload.contact,
    title: payload.title,
    email: payload.email,
    phone: payload.phone,
    representative_document: payload.representative_document,
    project: payload.project,
    address: payload.address,
    address_number: payload.address_number,
    district: payload.district,
    postal_code: payload.postal_code
  });
  assertEqual(fallbackFixture.refs.company.value, payload.legal_name, 'company fallback from legal_name');

  console.log(`ok ${result.filled}/${result.totalKeys}`);
}

run();
