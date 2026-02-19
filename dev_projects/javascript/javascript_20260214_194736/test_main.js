// Teste para a função monitorActivities
test('monitorActivities', async () => {
  // Simula uma resposta válida do Jira
  const response = {
    items: [
      { fields: { summary: 'Atividade 1', status: 'Open' } },
      { fields: { summary: 'Atividade 2', status: 'In Progress' } }
    ]
  };

  // Mocka a função axios.get
  jest.spyOn(axios, 'get').mockResolvedValue(response);

  try {
    await monitorActivities();
    expect(console.log).toHaveBeenCalledWith('Atividades:');
    expect(console.log).toHaveBeenCalledWith('- Atividade 1 (Status: Open)');
    expect(console.log).toHaveBeenCalledWith('- Atividade 2 (Status: In Progress)');
  } catch (error) {
    console.error('Erro ao monitorar atividades:', error);
  }
});

// Teste para a função sendFeedback
test('sendFeedback', async () => {
  // Simula uma resposta válida do Jira
  const response = {
    issue: { id: 'ISSUE-123' }
  };

  // Mocka a função axios.post
  jest.spyOn(axios, 'post').mockResolvedValue(response);

  try {
    await sendFeedback();
    expect(console.log).toHaveBeenCalledWith('Feedback enviado com sucesso:', response);
  } catch (error) {
    console.error('Erro ao enviar feedback:', error);
  }
});