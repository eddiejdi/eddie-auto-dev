using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;
using JiraNet;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

        // Função para registrar logs
        void Log(string message)
        {
            Console.WriteLine($"Log: {message}");
        }

        // Função para monitorar eventos
        async Task MonitorEvents()
        {
            var issues = await jiraClient.Issue.GetAllAsync();
            foreach (var issue in issues)
            {
                Log($"Issue: {issue.Key} - Status: {issue.Fields.Status.Name}");
            }
        }

        // Função para automatização de tarefas
        async Task AutomateTasks()
        {
            var tasks = await jiraClient.Task.GetAllAsync();
            foreach (var task in tasks)
            {
                Log($"Task: {task.Key} - Status: {task.Fields.Status.Name}");
                if (task.Fields.Status.Name == "To Do")
                {
                    try
                    {
                        await jiraClient.Issue.UpdateStatusAsync(task.Key, new IssueUpdateRequest { Status = new Status { Name = "In Progress" } });
                        Log($"Task updated to In Progress");
                    }
                    catch (Exception ex)
                    {
                        Log($"Error updating task: {ex.Message}");
                    }
                }
            }
        }

        // Função principal
        async Task Main()
        {
            try
            {
                await MonitorEvents();
                await AutomateTasks();
            }
            catch (Exception ex)
            {
                Log($"Error in main: {ex.Message}");
            }
        }
    }
}