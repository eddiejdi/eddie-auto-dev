using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration.Tests
{
    using Xunit;

    public class ProgramTests
    {
        private readonly JiraClient _jiraClient;

        public ProgramTests()
        {
            // Initialize the Jira client with your credentials
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
            this._jiraClient = jiraClient;
        }

        [Fact]
        public async Task TestCreateProject()
        {
            // Create a project
            var project = await _jiraClient.Projects.CreateAsync(new ProjectCreateRequest()
            {
                Key = "CSharpAgent",
                Name = "C# Agent",
                Description = "A tool for automating C# development tasks."
            });

            Assert.NotNull(project);
            Console.WriteLine($"Project created: {project.Key}");
        }

        [Fact]
        public async Task TestCreateBoard()
        {
            // Create a board
            var board = await _jiraClient.Boards.CreateAsync(new BoardCreateRequest()
            {
                Key = "CSharpAgentBoard",
                Name = "CSharp Agent Board",
                ProjectId = project.Id
            });

            Assert.NotNull(board);
            Console.WriteLine($"Board created: {board.Key}");
        }

        [Fact]
        public async Task TestCreateList()
        {
            // Create a list
            var list = await _jiraClient.Lists.CreateAsync(new ListCreateRequest()
            {
                Key = "CSharpAgentList",
                Name = "CSharp Agent List",
                BoardId = board.Id
            });

            Assert.NotNull(list);
            Console.WriteLine($"List created: {list.Key}");
        }

        [Fact]
        public async Task TestCreateIssueType()
        {
            // Create an issue type
            var issueType = await _jiraClient.IssueTypes.CreateAsync(new IssueTypeCreateRequest()
            {
                Key = "Bug",
                Name = "Bug",
                Description = "A problem with the software."
            });

            Assert.NotNull(issueType);
            Console.WriteLine($"Issue type created: {issueType.Key}");
        }

        [Fact]
        public async Task TestCreateIssue()
        {
            // Create an issue
            var project = await _jiraClient.Projects.CreateAsync(new ProjectCreateRequest()
            {
                Key = "CSharpAgent",
                Name = "C# Agent",
                Description = "A tool for automating C# development tasks."
            });

            var issue = await _jiraClient.Issues.CreateAsync(new IssueCreateRequest()
            {
                ProjectId = project.Id,
                Summary = "Initial setup of C# Agent",
                Description = "The first step in setting up the C# Agent.",
                PriorityId = 1, // High priority
                StatusId = 2, // Open status
                TypeId = issueType.Id,
                AssigneeId = null // No assignee initially
            });

            Assert.NotNull(issue);
            Console.WriteLine($"Issue created: {issue.Key}");
        }

        [Fact]
        public async Task TestAddCommentToIssue()
        {
            // Create an issue
            var project = await _jiraClient.Projects.CreateAsync(new ProjectCreateRequest()
            {
                Key = "CSharpAgent",
                Name = "C# Agent",
                Description = "A tool for automating C# development tasks."
            });

            var issue = await _jiraClient.Issues.CreateAsync(new IssueCreateRequest()
            {
                ProjectId = project.Id,
                Summary = "Initial setup of C# Agent",
                Description = "The first step in setting up the C# Agent.",
                PriorityId = 1, // High priority
                StatusId = 2, // Open status
                TypeId = issueType.Id,
                AssigneeId = null // No assignee initially
            });

            await _jiraClient.IssueComments.CreateAsync(issue.Key, new CommentCreateRequest()
            {
                Body = "Initial setup complete."
            });

            Assert.NotNull(issue);
            Console.WriteLine("Comment added to the issue.");
        }
    }
}