from flask import session
from db.mongo import users_collection, users_progression_collection, challenges_collection, roles_collection
from datetime import datetime, timezone

def prepare_base_context():

    # =========================
    # UTILISATEUR CONNECTÉ
    # =========================
    if "user_id" in session:
        user_id = session["user_id"]

        user = users_collection.find_one({"_id": user_id})

        if not user:
            # sécurité : user supprimé en DB
            session.clear()
            return prepare_base_context()

        username = user.get("username", "inconnu")
        role_name = user.get("role", "user")

        # récupérer permission depuis roles
        role_doc = roles_collection.find_one({"role_name": role_name})
        permission = role_doc["permission"] if role_doc else 2

        # progression utilisateur
        user_prog = users_progression_collection.find_one({"user_id": user_id})

        if not user_prog:
            users_progression_collection.insert_one({
                "user_id": user_id,
                "points": 0,
                "solved_challenges": [],
                "points_last_update": datetime.now(timezone.utc)
            })
            user_prog = {
                "points": 0,
                "solved_challenges": [],
                "points_last_update": datetime.now(timezone.utc)
            }

        solved_challenges = user_prog.get("solved_challenges", [])
        user_points = user_prog.get("points", 0)

        # =========================
        # RECALCUL INTELLIGENT (toutes les 5 min max)
        # =========================
        now = datetime.now(timezone.utc)
        last_update = user_prog.get("points_last_update")

        need_recalculate = False

        if not last_update:
            need_recalculate = True
        else:
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            if (now - last_update).total_seconds() > 300:
                need_recalculate = True

        if need_recalculate:
            challenges = list(challenges_collection.find())

            recalculated_points = sum(
                c.get("points", 0)
                for c in challenges
                if c["_id"] in solved_challenges
            )

            user_points = recalculated_points

            users_progression_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "points": recalculated_points,
                        "points_last_update": now
                    }
                }
            )

        # =========================
        # RANKING
        # =========================
        total_players = users_collection.count_documents({})
        rank = 0

        if total_players > 0:
            ranking = list(users_progression_collection.find().sort("points", -1))

            # filtrer users valides
            valid_user_ids = set(u["_id"] for u in users_collection.find({}, {"_id": 1}))
            ranking = [r for r in ranking if r["user_id"] in valid_user_ids]

            for i, entry in enumerate(ranking, start=1):
                if entry["user_id"] == user_id:
                    rank = i
                    break

        challenges = list(challenges_collection.find())
        max_points = sum(c.get("points", 0) for c in challenges) if challenges else 0

    # =========================
    # INVITÉ
    # =========================
    else:
        username = session.get("username", "Invité")
        role_name = session.get("role", "visitor")

        role_doc = roles_collection.find_one({"role_name": role_name})
        permission = role_doc["permission"] if role_doc else 2

        user_points = 0
        rank = 0
        total_players = 0
        max_points = 0
        solved_challenges = []

    # =========================
    # CONTEXTE FINAL
    # =========================
    return {
        "username": username,
        "role": role_name,
        "permission": permission,
        "points": user_points,
        "rank": rank,
        "total_players": total_players,
        "max_points": max_points,
        "solved_challenges": solved_challenges
    }