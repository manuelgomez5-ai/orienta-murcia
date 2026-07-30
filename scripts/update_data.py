from tracker.scraper import refresh_all

if __name__ == "__main__":
    state = refresh_all(max_publications=40)
    print(state)
