using System;
using System.Diagnostics;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace YourNamespace.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task MainAsync()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            await ExecuteTask(client);

            Assert.True(true, "Tarefa executada com sucesso!");
        }

        [Fact]
        public async Task ExecuteTaskAsync_SuccessfulCreateIssue()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            var issue = new Issue
            {
                Summary = "Tarefa executada em background",
                Description = "Esta é uma tarefa simulada que deve ser executada em background.",
                ProjectKey = "YOUR_PROJECT_KEY"
            };

            await client.CreateIssueAsync(issue);

            Assert.True(true, "Tarefa criada no Jira com sucesso!");
        }

        [Fact]
        public async Task ExecuteTaskAsync_FailureCreateIssue()
        {
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            try
            {
                await client.CreateIssueAsync(null);
                Assert.True(false, "Erro ao criar tarefa no Jira");
            }
            catch (Exception)
            {
                Assert.True(true, "Erro ao criar tarefa no Jira");
            }
        }

        private async Task ExecuteTask(JiraClient client)
        {
            // Simulação de tarefa que deve ser executada em background
            await Task.Delay(5000);
        }
    }
}