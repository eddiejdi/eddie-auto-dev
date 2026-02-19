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
            // Initialize the Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Create a project
            var project = await jiraClient.Projects.CreateAsync(new ProjectCreateRequest()
            {
                Key = "CSharpAgent",
                Name = "C# Agent",
                Description = "A tool for automating C# development tasks."
            });

            Console.WriteLine($"Project created: {project.Key}");

            // Create a board
            var board = await jiraClient.Boards.CreateAsync(new BoardCreateRequest()
            {
                Key = "CSharpAgentBoard",
                Name = "CSharp Agent Board",
                ProjectId = project.Id
            });

            Console.WriteLine($"Board created: {board.Key}");

            // Create a list
            var list = await jiraClient.Lists.CreateAsync(new ListCreateRequest()
            {
                Key = "CSharpAgentList",
                Name = "CSharp Agent List",
                BoardId = board.Id
            });

            Console.WriteLine($"List created: {list.Key}");

            // Create an issue type
            var issueType = await jiraClient.IssueTypes.CreateAsync(new IssueTypeCreateRequest()
            {
                Key = "Bug",
                Name = "Bug",
                Description = "A problem with the software."
            });

            Console.WriteLine($"Issue type created: {issueType.Key}");

            // Create an issue
            var issue = await jiraClient.Issues.CreateAsync(new IssueCreateRequest()
            {
                ProjectId = project.Id,
                Summary = "Initial setup of C# Agent",
                Description = "The first step in setting up the C# Agent.",
                PriorityId = 1, // High priority
                StatusId = 2, // Open status
                TypeId = issueType.Id,
                AssigneeId = null // No assignee initially
            });

            Console.WriteLine($"Issue created: {issue.Key}");

            // Add a comment to the issue
            await jiraClient.IssueComments.CreateAsync(issue.Key, new CommentCreateRequest()
            {
                Body = "Initial setup complete."
            });

            Console.WriteLine("Comment added to the issue.");
        }
    }
}