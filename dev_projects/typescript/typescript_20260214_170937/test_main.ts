// Teste para a função startIntegration da classe TypeScriptAgentJira
test('startIntegration', async () => {
    const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'YOUR_USERNAME',
        password: 'YOUR_PASSWORD'
    });

    const agent = new Agent();

    const integration = new TypeScriptAgentJira(jiraClient, agent);

    // Caso de sucesso
    await integration.startIntegration();
    expect(console.log).toHaveBeenCalledWith('Iniciando integração TypeScript Agent com Jira...');

    // Caso de erro (autenticação falhada)
    jest.spyOn(integration.jiraClient, 'authenticate').mockRejectedValue(new Error('Erro ao autenticar no Jira'));
    await integration.startIntegration();
    expect(console.error).toHaveBeenCalledWith('Erro durante a integração:', new Error('Erro ao autenticar no Jira:'));
});

// Teste para a função authenticate da classe TypeScriptAgentJira
test('authenticate', async () => {
    const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'YOUR_USERNAME',
        password: 'YOUR_PASSWORD'
    });

    const agent = new Agent();

    const integration = new TypeScriptAgentJira(jiraClient, agent);

    // Caso de sucesso
    await integration.authenticate();
    expect(console.log).toHaveBeenCalledWith('Autenticação bem-sucedida!');

    // Caso de erro (autenticação falhada)
    jest.spyOn(integration.jiraClient, 'authenticate').mockRejectedValue(new Error('Erro ao autenticar no Jira'));
    await integration.authenticate();
    expect(console.error).toHaveBeenCalledWith('Erro durante a integração:', new Error('Erro ao autenticar no Jira:'));
});

// Teste para a função createIssue da classe TypeScriptAgentJira
test('createIssue', async () => {
    const jiraClient = new JiraClient({
        url: 'https://your-jira-instance.atlassian.net',
        username: 'YOUR_USERNAME',
        password: 'YOUR_PASSWORD'
    });

    const agent = new Agent();

    const integration = new TypeScriptAgentJira(jiraClient, agent);

    // Caso de sucesso
    await integration.createIssue();
    expect(console.log).toHaveBeenCalledWith('Issue criado:', 'ISSUE_KEY');

    // Caso de erro (criação do issue falhada)
    jest.spyOn(integration.jiraClient, 'createIssue').mockRejectedValue(new Error('Erro ao criar o issue no Jira'));
    await integration.createIssue();
    expect(console.error).toHaveBeenCalledWith('Erro durante a integração:', new Error('Erro ao criar o issue no Jira:'));
});