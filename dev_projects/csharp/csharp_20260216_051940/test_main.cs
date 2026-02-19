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
        private readonly JiraClient _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        [Fact]
        public async Task CreateTask_Successful()
        {
            var title = "New Task Title";
            var description = "Description of the task";

            await CreateTask(_jiraClient, title, description);

            // Verifique se a tarefa foi criada com sucesso
            var createdTask = await _jiraClient.GetIssueByIdAsync(12345);
            Assert.NotNull(createdTask);
        }

        [Fact]
        public async Task CreateTask_InvalidTitle()
        {
            var title = "";
            var description = "Description of the task";

            try
            {
                await CreateTask(_jiraClient, title, description);
            }
            catch (Exception ex)
            {
                // Verifique se a exceção é correta
                Assert.Contains("The value cannot be null or empty.", ex.Message);
            }
        }

        [Fact]
        public async Task UpdateTask_Successful()
        {
            var taskId = 12345;
            var newTitle = "Updated Task Title";

            await CreateTask(_jiraClient, "Original Title", "Description of the task");

            await UpdateTask(_jiraClient, taskId, newTitle);

            // Verifique se a tarefa foi atualizada com sucesso
            var updatedTask = await _jiraClient.GetIssueByIdAsync(taskId);
            Assert.NotNull(updatedTask);
            Assert.Equal(newTitle, updatedTask.Summary);
        }

        [Fact]
        public async Task UpdateTask_InvalidNewTitle()
        {
            var taskId = 12345;
            var newTitle = "";

            try
            {
                await UpdateTask(_jiraClient, taskId, newTitle);
            }
            catch (Exception ex)
            {
                // Verifique se a exceção é correta
                Assert.Contains("The value cannot be null or empty.", ex.Message);
            }
        }

        [Fact]
        public async Task DeleteTask_Successful()
        {
            var taskId = 12345;

            await CreateTask(_jiraClient, "Original Title", "Description of the task");

            await DeleteTask(_jiraClient, taskId);

            // Verifique se a tarefa foi deletada com sucesso
            try
            {
                await _jiraClient.GetIssueByIdAsync(taskId);
            }
            catch (Exception ex)
            {
                // Verifique se a exceção é correta
                Assert.Contains("The issue with ID 12345 does not exist.", ex.Message);
            }
        }

        [Fact]
        public async Task DeleteTask_InvalidTaskId()
        {
            var taskId = -1;

            try
            {
                await DeleteTask(_jiraClient, taskId);
            }
            catch (Exception ex)
            {
                // Verifique se a exceção é correta
                Assert.Contains("The issue with ID -1 does not exist.", ex.Message);
            }
        }
    }
}