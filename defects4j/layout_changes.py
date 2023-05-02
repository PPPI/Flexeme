import argparse
import csv
import subprocess


def get_commit_date(commit_id, repo_path):
    # Call the `git log` command to get the commit date
    command = ['git', 'log', '-1', '--format=%cd', '--date=iso', commit_id]
    output = subprocess.check_output(command, cwd=repo_path)

    # Convert the output to a string and strip whitespace
    date_str = output.decode('utf-8').strip()

    return date_str


def sort_commits_by_date(commit_csv, repo_path):
    # Open the CSV file and read the data into a list
    with open(commit_csv, 'r') as f:
        reader = csv.reader(f)
        data = list(reader)

    # Get the date for each commit ID using the `get_commit_date()` function
    commits_with_dates = []
    for row in data:
        commit_id = row[0]
        commit_date = get_commit_date(commit_id, repo_path)
        commits_with_dates.append({'commit_id': commit_id, 'date': commit_date})

    # Sort the data by the date column
    sorted_data = sorted(commits_with_dates, key=lambda row: row['date'])

    # Return the sorted data as a list of dictionaries
    return sorted_data


def main():
    # Define command-line arguments for the commit CSV file path and the repository path
    parser = argparse.ArgumentParser()
    parser.add_argument('commit_csv', help='path to CSV file containing commit IDs')
    parser.add_argument('repo_path', help='path to repository containing the commits')
    args = parser.parse_args()

    # Sort the commits by date
    sorted_commits = sort_commits_by_date(args.commit_csv, args.repo_path)

    # Print the sorted data to the console
    for row in sorted_commits:
        print(row['commit_id'], row['date'])


if __name__ == '__main__':
    main()
