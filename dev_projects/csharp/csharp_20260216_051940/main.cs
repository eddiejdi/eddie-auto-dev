using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Configuração do cliente Jira
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Função para criar uma nova tarefa no Jira
            await CreateTask(jiraClient, "New Task Title", "Description of the task");

            // Função para atualizar uma tarefa existente no Jira
            await UpdateTask(jiraClient, 12345, "Updated Task Title");

            // Função para deletar uma tarefa do Jira
            await DeleteTask(jiraClient, 12345);
        }

        static async Task CreateTask(JiraClient jiraClient, string title, string description)
        {
            var task = new Issue()
            {
                Summary = title,
                Description = description,
                ProjectId = 10000 // ID do projeto
            };

            await jiraClient.CreateIssueAsync(task);
            Console.WriteLine("Task created successfully.");
        }

        static async Task UpdateTask(JiraClient jiraClient, int taskId, string newTitle)
        {
            var issue = await jiraClient.GetIssueByIdAsync(taskId);

            if (issue != null)
            {
                issue.Summary = newTitle;
                await jiraClient.UpdateIssueAsync(issue);
                Console.WriteLine("Task updated successfully.");
            }
            else
            {
                Console.WriteLine("Task not found.");
            }
        }

        static async Task DeleteTask(JiraClient jiraClient, int taskId)
        {
            var issue = await jiraClient.GetIssueByIdAsync(taskId);

            if (issue != null)
            {
                await jiraClient.DeleteIssueAsync(issue);
                Console.WriteLine("Task deleted successfully.");
            }
            else
            {
                Console.WriteLine("Task not found.");
            }
        }
    }
}