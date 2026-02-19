// Teste da função fetchActivities
test('fetchActivities', async () => {
  // Simula uma resposta válida
  const mockResponse = { data: [{ activityId: '12345' }] };
  axios.get.mockResolvedValue(mockResponse);

  try {
    const result = await fetchActivities();
    expect(result).toEqual([{ activityId: '12345' }]);
  } catch (error) {
    fail('fetchActivities deve retornar uma lista de atividades válidas');
  }
});

// Teste da função hasProblems
test('hasProblems', () => {
  const activities = [{ status: 'ERROR' }, { status: 'SUCCESS' }];
  expect(hasProblems(activities)).toBe(true);
});

// Teste da função integrateJavaScriptAgentWithJira
test('integrateJavaScriptAgentWithJira', async () => {
  // Simula uma resposta válida para fetchActivities
  const mockResponse = { data: [{ activityId: '12345' }] };
  axios.get.mockResolvedValue(mockResponse);

  try {
    await integrateJavaScriptAgentWithJira();
    expect(logger.info).toHaveBeenCalledWith('Atividades coletadas:', mockResponse.data);
    expect(logger.error).not.toHaveBeenCalledWith('Alerta: Problemas encontrados');
  } catch (error) {
    fail('integrateJavaScriptAgentWithJira deve integrar com Jira corretamente');
  }
});