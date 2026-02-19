const axios = require('axios');
const fs = require('fs');

describe('sendToJira', () => {
  it('envia dados para Jira com sucesso', async () => {
    const data = { summary: 'Teste de envio', assignee: 'John Doe' };
    await sendToJira(data);
    expect(console.log).toHaveBeenCalledWith('Dados enviados para Jira com sucesso:', { summary: 'Teste de envio', assignee: 'John Doe' });
  });

  it('envia dados para Jira com erro', async () => {
    const data = { summary: '', assignee: '' };
    await sendToJira(data);
    expect(console.error).toHaveBeenCalledWith('Erro ao enviar dados para Jira:', new Error('Dados inválidos'));
  });
});

describe('monitorActivities', () => {
  it('monita atividades com sucesso', async () => {
    const data = { summary: 'Teste de monitoramento', assignee: 'John Doe' };
    await monitorActivities();
    expect(console.log).toHaveBeenCalledWith('Atividades monitoradas:', { summary: 'Teste de monitoramento', assignee: 'John Doe' });
  });

  it('monita atividades com erro', async () => {
    const data = { summary: '', assignee: '' };
    await monitorActivities();
    expect(console.error).toHaveBeenCalledWith('Erro ao monitorar atividades:', new Error('Dados inválidos'));
  });
});

describe('manageTasks', () => {
  it('gerencia tarefas com sucesso', async () => {
    const data = { summary: 'Teste de gerenciamento', assignee: 'John Doe' };
    await manageTasks();
    expect(console.log).toHaveBeenCalledWith('Tarefas gerenciadas:', { summary: 'Teste de gerenciamento', assignee: 'John Doe' });
  });

  it('gerencia tarefas com erro', async () => {
    const data = { summary: '', assignee: '' };
    await manageTasks();
    expect(console.error).toHaveBeenCalledWith('Erro ao gerenciar tarefas:', new Error('Dados inválidos'));
  });
});

describe('main', () => {
  it('executa o programa com sucesso', async () => {
    try {
      await main();
    } catch (error) {
      console.error('Erro no sistema:', error);
    }
  });

  it('executa o programa com erro', async () => {
    try {
      await main();
    } catch (error) {
      expect(console.error).toHaveBeenCalledWith('Erro no sistema:', new Error('Erro ao executar o programa'));
    }
  });
});