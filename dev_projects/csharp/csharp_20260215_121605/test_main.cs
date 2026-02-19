using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

namespace YourNamespace.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateTaskAsync_Success()
        {
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            await jira.CreateIssueAsync(
                "Bug",
                new Dictionary<string, object>
                {
                    { "summary", "Implement SCRUM-14" },
                    { "description", "Integrating C# Agent with Jira" }
                });

            // Verifique se a tarefa foi criada com sucesso
        }

        [Fact]
        public async Task CreateTaskAsync_Failure()
        {
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                await jira.CreateIssueAsync(
                    "Bug",
                    new Dictionary<string, object>
                    {
                        { "summary", "" },
                        { "description", "" }
                    }
                );
            }
            catch (Exception ex)
            {
                // Verifique se o erro é esperado
            }
        }

        [Fact]
        public async Task MonitorTasksAsync_Success()
        {
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            var issues = await jira.GetIssuesAsync("Bug");

            foreach (var issue in issues)
            {
                // Verifique se as tarefas foram monitoradas corretamente
            }
        }

        [Fact]
        public async Task MonitorTasksAsync_Failure()
        {
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

            try
            {
                await jira.GetIssuesAsync("Invalid");
            }
            catch (Exception ex)
            {
                // Verifique se o erro é esperado
            }
        }
    }
}