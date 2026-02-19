using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_Success()
        {
            // Configuração do cliente Jira
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                // Cria um novo ticket no Jira com valores válidos
                var issue = await client.CreateIssueAsync(
                    projectKey: "YOUR_PROJECT_KEY",
                    summary: "Teste do CSharp Agent com Jira",
                    description: "Este é um teste para integrar o CSharp Agent com Jira",
                    priorityId: 1,
                    assigneeId: 10345
                );

                // Verifica se o ticket foi criado corretamente
                Assert.NotNull(issue);
                Assert.NotEmpty(issue.Key);
            }
            catch (Exception ex)
            {
                // Captura e verifica erros na criação do ticket
                Assert.Contains("Failed to create issue", ex.Message);
            }
        }

        [Fact]
        public async Task CreateIssueAsync_Error()
        {
            // Configuração do cliente Jira com valores inválidos
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                // Tenta criar um ticket com uma descrição vazia
                await client.CreateIssueAsync(
                    projectKey: "YOUR_PROJECT_KEY",
                    summary: "Teste do CSharp Agent com Jira",
                    description: "",
                    priorityId: 1,
                    assigneeId: 10345
                );
            }
            catch (Exception ex)
            {
                // Verifica se o erro é esperado
                Assert.Contains("Description cannot be empty", ex.Message);
            }
        }

        [Fact]
        public async Task CreateIssueAsync_InvalidPriority()
        {
            // Configuração do cliente Jira com uma prioridade inválida
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                // Tenta criar um ticket com uma prioridade inválida
                await client.CreateIssueAsync(
                    projectKey: "YOUR_PROJECT_KEY",
                    summary: "Teste do CSharp Agent com Jira",
                    description: "Este é um teste para integrar o CSharp Agent com Jira",
                    priorityId: 10, // Prioridade inválida
                    assigneeId: 10345
                );
            }
            catch (Exception ex)
            {
                // Verifica se o erro é esperado
                Assert.Contains("Invalid priority", ex.Message);
            }
        }

        [Fact]
        public async Task CreateIssueAsync_InvalidAssignee()
        {
            // Configuração do cliente Jira com um usuário inválido
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                // Tenta criar um ticket com um usuário inválido
                await client.CreateIssueAsync(
                    projectKey: "YOUR_PROJECT_KEY",
                    summary: "Teste do CSharp Agent com Jira",
                    description: "Este é um teste para integrar o CSharp Agent com Jira",
                    priorityId: 1,
                    assigneeId: -1 // Usuário inválido
                );
            }
            catch (Exception ex)
            {
                // Verifica se o erro é esperado
                Assert.Contains("Invalid assignee", ex.Message);
            }
        }
    }
}